#!/usr/bin/env python
"""
Script de test pour reproduire le problème d'analyse avec les conditions de production.
"""

import os
import django
import sys
import json

# Setup Django environment
sys.path.append('/home/jonas/Gits/Hypostasia/Hypostasia-V3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Page, Prompt, Argument
from core.services import build_full_prompt, dispatch_llm_request

def test_page_analysis(page_id):
    """Test l'analyse d'une page spécifique"""
    print(f"\n{'='*80}")
    print(f"TEST: Analyse de la page {page_id}")
    print(f"{'='*80}\n")
    
    # Récupérer la page
    try:
        page = Page.objects.get(id=page_id)
    except Page.DoesNotExist:
        print(f"❌ Page {page_id} n'existe pas")
        return
    
    print(f"📄 URL: {page.url}")
    print(f"📏 Longueur du texte: {len(page.text_readability)} caractères")
    print(f"📊 Arguments actuels: {page.arguments.count()}")
    
    # Récupérer le prompt
    prompt = Prompt.objects.filter(name="Analyse Standard Hypostasia").first()
    if not prompt:
        print("❌ Prompt 'Analyse Standard Hypostasia' non trouvé")
        return
    
    print(f"\n🔧 Prompt: {prompt.name}")
    print(f"🤖 Modèle: {prompt.default_model.name if prompt.default_model else 'None'}")
    print(f"📝 Inputs: {prompt.inputs.count()}")
    
    # Afficher les inputs du prompt
    print("\n📋 Structure du prompt:")
    for inp in prompt.inputs.order_by('order'):
        print(f"  {inp.order}. {inp.name} ({inp.role})")
        print(f"     Longueur: {len(inp.content)} chars")
    
    # Construire le prompt complet
    full_prompt = build_full_prompt(page, prompt)
    print(f"\n📏 Prompt complet: {len(full_prompt)} caractères")
    
    # Afficher un extrait du prompt
    print("\n📄 Extrait du prompt (premiers 500 chars):")
    print("-" * 80)
    print(full_prompt[:500])
    print("-" * 80)
    
    # Afficher la fin du prompt pour voir le texte à analyser
    print("\n📄 Extrait du prompt (derniers 500 chars):")
    print("-" * 80)
    print(full_prompt[-500:])
    print("-" * 80)
    
    return prompt, page, full_prompt


def test_api_call(page_id, actually_call_api=False):
    """Test l'appel réel à l'API"""
    prompt, page, full_prompt = test_page_analysis(page_id)
    
    if not actually_call_api:
        print("\n⚠️  Mode DRY-RUN: Pour tester l'appel réel à l'API, utilisez --test-api")
        print("    (cela consommera des crédits API)")
        return
    
    # Tester l'appel à l'API
    print("\n" + "="*80)
    print("🚀 APPEL API RÉEL")
    print("="*80 + "\n")
    
    try:
        response = dispatch_llm_request(prompt.default_model, full_prompt, page)
        print(f"\n✅ Réponse reçue ({len(response)} chars)")
        print("\n📄 Réponse brute (premiers 1000 chars):")
        print("-" * 80)
        print(response[:1000])
        if len(response) > 1000:
            print(f"\n... ({len(response) - 1000} chars supplémentaires)")
        print("-" * 80)
        
        # Essayer de parser
        try:
            data = json.loads(response)
            print(f"\n✅ JSON valide")
            print(f"Type: {type(data)}")
            if isinstance(data, dict):
                print(f"Clés: {list(data.keys())}")
                # Try to find the array
                for key, value in data.items():
                    if isinstance(value, list):
                        print(f"  → Clé '{key}' contient une liste de {len(value)} éléments")
            elif isinstance(data, list):
                print(f"Nombre d'éléments: {len(data)}")
                if len(data) > 0:
                    print(f"Premier élément: {list(data[0].keys()) if isinstance(data[0], dict) else data[0]}")
        except json.JSONDecodeError as e:
            print(f"\n❌ Erreur de parsing JSON: {e}")
            
    except Exception as e:
        print(f"\n❌ Erreur lors de l'appel API: {e}")
        import traceback
        traceback.print_exc()


def show_all_pages():
    """Affiche toutes les pages avec leurs statistiques"""
    print(f"\n{'='*80}")
    print("TOUTES LES PAGES")
    print(f"{'='*80}\n")
    
    pages = Page.objects.all().order_by('id')
    print(f"Total: {pages.count()} pages\n")
    
    for page in pages:
        args_count = page.arguments.count()
        text_len = len(page.text_readability)
        status_icon = "✅" if args_count > 5 else "⚠️" if args_count > 0 else "❌"
        
        print(f"{status_icon} Page {page.id:2d}: {args_count:2d} args | {text_len:6d} chars | {page.url[:70]}")

def inspect_prompt_content():
    """Affiche le contenu complet du prompt"""
    print(f"\n{'='*80}")
    print("CONTENU DU PROMPT")
    print(f"{'='*80}\n")
    
    prompt = Prompt.objects.filter(name="Analyse Standard Hypostasia").first()
    if not prompt:
        print("❌ Prompt non trouvé")
        return
    
    for inp in prompt.inputs.order_by('order'):
        print(f"\n{'─'*80}")
        print(f"📋 {inp.order}. {inp.name} ({inp.role})")
        print(f"{'─'*80}")
        print(inp.content)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test de l'analyse Hypostasia")
    parser.add_argument('--page', type=int, help='ID de la page à tester')
    parser.add_argument('--all', action='store_true', help='Afficher toutes les pages')
    parser.add_argument('--prompt', action='store_true', help='Afficher le contenu du prompt')
    parser.add_argument('--test-api', action='store_true', help='Tester l\'appel réel à l\'API (consomme des crédits)')
    
    args = parser.parse_args()
    
    if args.all:
        show_all_pages()
    elif args.prompt:
        inspect_prompt_content()
    elif args.page:
        if args.test_api:
            test_api_call(args.page, actually_call_api=True)
        else:
            test_api_call(args.page, actually_call_api=False)
    else:
        print("Usage:")
        print("  python test_analysis.py --all                # Afficher toutes les pages")
        print("  python test_analysis.py --prompt             # Afficher le prompt complet")
        print("  python test_analysis.py --page 15            # Analyser la page 15 (dry-run)")
        print("  python test_analysis.py --page 15 --test-api # Tester l'API réellement (consomme des crédits)")
