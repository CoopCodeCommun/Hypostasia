
import os
import django
import sys

# Setup Django environment
sys.path.append('/home/jonas/Gits/Test antigravity/V3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Prompt, AIModel

def inspect_config():
    print("--- Inspecting DB Configuration ---")
    
    print("\n[AI Models]")
    for model in AIModel.objects.all():
        print(f"ID: {model.id} | Name: {model.name} | Provider: {model.provider} | Active: {model.is_active}")
        
    print("\n[Prompts]")
    for prompt in Prompt.objects.all():
        model_name = prompt.default_model.name if prompt.default_model else "None (Mock Fallback)"
        print(f"ID: {prompt.id} | Name: {prompt.name} | Default Model: {model_name}")

if __name__ == "__main__":
    inspect_config()
