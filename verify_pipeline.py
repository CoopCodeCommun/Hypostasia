
import os
import django
import sys
import time

# Setup Django environment
sys.path.append('/home/jonas/Gits/Test antigravity/V3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Page, Prompt

try:
    from core.services import run_analysis_pipeline
except ImportError:
    # Handle case where services.py changes are not yet reloaded if running in shell (not issue here but good practice)
    pass

def verify_pipeline():
    print("--- Verifying AI Pipeline on Last 4 Pages ---")
    
    # 1. Get the prompt
    prompt = Prompt.objects.filter(name="Analyse Standard Hypostasia").first()
    if not prompt:
        print("Error: Prompt not found. Run seed_prompts.py first.")
        return
        
    print(f"Using Prompt: {prompt.name}")
    if prompt.default_model:
        print(f"Using Model: {prompt.default_model.name} ({prompt.default_model.provider})")
    else:
        print("Using Model: Fallback Mock")

    # 2. Get pages
    pages = Page.objects.order_by('-updated_at')[:4]
    
    if not pages:
        print("No pages found.")
        return

    for i, page in enumerate(pages):
        print(f"\n[{i+1}/4] Processing Page ID {page.id}: {page.url}")
        print(f"Title: {page.html_readability[:50].replace('<', '[').replace('>', ']')}...") 

        # 3. Run Pipeline
        print("Running pipeline...")
        start_time = time.time()
        try:
            count = run_analysis_pipeline(page, prompt)
            duration = time.time() - start_time
            print(f"Pipeline finished in {duration:.2f}s. Arguments created: {count}")
            
            # 4. Inspect result
            if count > 0:
                first_arg = page.arguments.first()
                print(f"  > First Arg Summary: {first_arg.summary}")
                print(f"  > First Arg Quote: {first_arg.text_original[:80]}...")
                
                # Check for Mock signature
                is_mock = "Simulé par MockLLM" in first_arg.summary or "Mock" in first_arg.summary
                if is_mock:
                    print("  [FAIL] This argument seems to be MOCKED (contains 'Mock').")
                else:
                    print("  [SUCCESS] This argument appears to be REAL (No mock signature).")
            else:
                print("  [WARN] No arguments generated. (Text might be empty or LLM failed)")
        except Exception as e:
            print(f"  [ERROR] Pipeline crashed: {e}")

if __name__ == "__main__":
    verify_pipeline()
