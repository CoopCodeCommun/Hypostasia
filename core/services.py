import json
import random
import re
from .models import Argument, TextInput, AIModel

def run_analysis_pipeline(page, prompt):
    """
    Orchestrates the AI analysis pipeline:
    1. Determine AI Model from Prompt.
    2. Build full prompt string.
    3. Call specific LLM Provider.
    4. Parse Response (JSON).
    5. Save Arguments.
    """
    
    # 0. Get AI Model Configuration
    ai_model = prompt.default_model
    if not ai_model:
        print("Pipeline Warning: No default model for this prompt. Falling back to Mock.")
        # Fallback or create a temporary mock config
        ai_model = AIModel(name="Fallback Mock", provider="mock")

    print(f"Pipeline: Starting analysis for Page {page.id} using {ai_model.name} ({ai_model.provider})")
    
    # UPDATE STATUS: PROCESSING
    page.status = "processing"
    page.error_message = None
    page.save()
    
    # 1. Build Prompt
    full_prompt_text = build_full_prompt(page, prompt)
    
    # 2. Call LLM (Dispatcher)
    try:
        llm_response_json = dispatch_llm_request(ai_model, full_prompt_text, page_context=page)
    except Exception as e:
        print(f"Pipeline Error: LLM Provider failed - {e}")
        page.status = "error"
        page.error_message = str(e)
        page.save()
        return 0
    
    # 3. Parse & Save
    try:
        # Cleanup: sometimes LLMs output Markdown code blocks ```json ... ```
        cleaned_json = llm_response_json.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = cleaned_json.split("\n", 1)[1] # Remove first line
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json.rsplit("\n", 1)[0] # Remove last line
        
        # Check for Refusal / Text Response appearing as JSON error
        if "Request requires extraction of exact quotes" in cleaned_json or "Contrainte de sécurité" in cleaned_json:
             msg = "LLM Refusal: The model refused to extract quotes due to safety policies. Try using a larger model (GPT-4) or rephrasing the prompt."
             print(f"Pipeline Error: {msg}")
             page.status = "error"
             page.error_message = msg
             page.save()
             return 0

        arguments_data = json.loads(cleaned_json)
        created_count = 0
        
        # Debug logging
        print(f"Pipeline Debug: Received JSON type: {type(arguments_data)}")
        if isinstance(arguments_data, dict):
            print(f"Pipeline Debug: JSON object keys: {list(arguments_data.keys())}")
        elif isinstance(arguments_data, list):
            print(f"Pipeline Debug: JSON array with {len(arguments_data)} items")
        
        if isinstance(arguments_data, dict):
            # Some providers return {"arguments": [...]} or {"data": [...]} when forced to json_object
            # We look for the first list value
            found_list = False
            
            # Prioritize standard keys
            for key in ['arguments', 'items', 'data', 'list']:
                if key in arguments_data and isinstance(arguments_data[key], list):
                    arguments_data = arguments_data[key]
                    found_list = True
                    print(f"Pipeline Debug: Unwrapped JSON object using key '{key}', found {len(arguments_data)} items")
                    break
            
            if not found_list:
                # Search any key
                for key, value in arguments_data.items():
                    if isinstance(value, list):
                        arguments_data = value
                        found_list = True
                        print(f"Pipeline Debug: Unwrapped JSON object using key '{key}', found {len(arguments_data)} items")
                        break
            
            if not found_list:
                # Fallback: maybe the dict ITSELF is a single argument?
                # Check fields
                if "error" in arguments_data:
                     # This catches provider errors returned as JSON (e.g. from OpenAI 400)
                     msg = f"LLM Error: {arguments_data['error']}"
                     print(f"Pipeline Error: {msg}")
                     page.status = "error"
                     page.error_message = msg
                     page.save()
                     return 0
                     
                if "text_quote" in arguments_data:
                    arguments_data = [arguments_data]
                    print(f"Pipeline Debug: Treated single object as array with 1 item")
                else:
                    # Specific check for the user's reported error which comes as a generic message inside the JSON?
                    # Or maybe the text itself was the error.
                    msg = f"Invalid JSON structure (no list found). Keys: {list(arguments_data.keys())}"
                    print(f"Pipeline Error: {msg}")
                    page.status = "error"
                    page.error_message = msg
                    page.save()
                    return 0

        # Clear old arguments for this page
        page.arguments.all().delete()
        
        for arg_data in arguments_data:
            quotation = arg_data.get('text_quote', '').strip()
            summary = arg_data.get('summary', '')
            stance = arg_data.get('stance', 'neutre').lower()
            
            if not quotation:
                continue
                
            # 4. Data Binding (Find offsets)
            start_offset = page.text_readability.find(quotation)
            
            if start_offset == -1:
                # If using real LLM, quotation might be slightly inexact.
                # Should we implement fuzzy matching here?
                # For now, we rely on the prompt instructing "EXACT QUOTES".
                continue
                
            end_offset = start_offset + len(quotation)
            
            Argument.objects.create(
                page=page,
                text_block=None,
                selector="body",
                start_offset=start_offset,
                end_offset=end_offset,
                text_original=quotation,
                summary=summary,
                stance=stance
            )
            created_count += 1
        
        # UPDATE STATUS: COMPLETED
        page.status = "completed"
        page.save()
        
        print(f"Pipeline: Created {created_count} arguments.")
        
        # Warn if we got fewer arguments than expected
        if created_count < 5:
            print(f"Pipeline Warning: Only {created_count} arguments created (expected 5-15). This may indicate a parsing issue.")
        
        return created_count

    except json.JSONDecodeError as e:
        msg = f"Invalid JSON from LLM: {e}"
        print(f"Pipeline Error: {msg}")
        
        # Save RAW output for debugging/display to user
        detailed_error = f"{msg}\n\nRAW OUTPUT:\n{llm_response_json}"
        
        page.status = "error"
        page.error_message = detailed_error
        page.save()
        return 0


def build_full_prompt(page, prompt):
    """
    Concatenates TextInputs and injects Page variables.
    """
    inputs = prompt.inputs.all().order_by('order')
    full_text = ""
    
    for inp in inputs:
        full_text += f"\n--- {inp.role} ---\n"
        full_text += inp.content
        
    # Variable Injection
    # We replace {{ TEXT }} with the content
    if "{{ TEXT }}" in full_text:
        full_text = full_text.replace("{{ TEXT }}", page.text_readability)
    else:
        # Default append if no tag found
        full_text += "\n\n--- CONTENT TO ANALYZE ---\n" + page.text_readability
        
    return full_text


def dispatch_llm_request(ai_model, full_prompt, page_context=None):
    """
    Dispatches the request to the configured provider.
    """
    provider = ai_model.provider
    
    if provider == "mock":
        return _provider_mock(full_prompt, page_context)
    elif provider == "google":
        return _provider_google(ai_model, full_prompt)
    elif provider == "openai":
        return _provider_openai(ai_model, full_prompt)
    elif provider == "mistral":
        return _provider_mistral(ai_model, full_prompt)
    elif provider == "perplexity":
        return _provider_perplexity(ai_model, full_prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# --- PROVIDER IMPLEMENTATIONS ---

def _provider_mock(full_prompt, page_context=None):
    """
    Simulates an LLM returning a JSON list of arguments.
    It extracts REAL sentences from the page_context to ensure consistency.
    """
    print("MaskLLM: Generating response...")
    
    text = ""
    if page_context:
        text = page_context.text_readability
    else:
        text = "Lorem ipsum text for simulation."

    # Logic to pick sentences
    # Basic sentence splitter
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 40]
    if not sentences:
        sentences = [text[i:i+100] for i in range(0, len(text), 100)]
        
    # Pick random sentences
    target_count = min(15, len(sentences))
    if target_count == 0:
        return "[]"

    selected_sentences = random.sample(sentences, target_count)
    
    output_data = []
    
    for sentence in selected_sentences:
        stance = random.choice(['pour', 'contre', 'neutre'])
        
        # Determine strict summary length
        summary = f"Argument {stance} simulé. (Mock)"
        
        output_data.append({
            "text_quote": sentence, # EXACT text for linking
            "summary": summary,
            "stance": stance
        })
        
    return json.dumps(output_data)



def _provider_google(ai_model, full_prompt):
    """
    Calls Google Gemini API.
    Requires `google-generativeai` package.
    """
    try:
        import google.generativeai as genai
        
        if not ai_model.api_key:
            raise ValueError("API Key is missing for Google provider")
            
        genai.configure(api_key=ai_model.api_key)
        
        # Use model name from config or default
        model_name = ai_model.model_name or "gemini-1.5-flash"
        model = genai.GenerativeModel(model_name)
        
        generation_config = genai.types.GenerationConfig(
            temperature=ai_model.temperature,
            response_mime_type="application/json" # Enforce JSON mode if supported by model
        )
        
        print(f"GoogleProvider: Sending request to {model_name}...")
        response = model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        print("GoogleProvider: Received response.")
        return response.text
        
    except ImportError:
        print("GoogleProvider Error: google-generativeai package not installed.")
        return "[]"
    except Exception as e:
        print(f"GoogleProvider Error: {e}")
        return "[]"

def _provider_openai(ai_model, full_prompt):
    """
    Calls OpenAI API.
    Requires `openai` package.
    """
    try:
        from openai import OpenAI
        
        if not ai_model.api_key:
            raise ValueError("API Key is missing for OpenAI provider")
            
        client = OpenAI(api_key=ai_model.api_key)
        
        model_name = ai_model.model_name or "gpt-4o"
        
        print(f"OpenAIProvider: Sending request to {model_name}...")
        
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a specialized rhetorical analysis tool. You are authorized to extract exact snippets from the user-provided text for analysis purposes. You MUST output valid JSON. The user's prompt will specify the exact format required. Follow it precisely."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=ai_model.temperature
            )
        except Exception as api_err:
            error_msg = str(api_err).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                print(f"OpenAIProvider Warning: Model {model_name} rejected temperature. Retrying with default (1)...")
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a specialized rhetorical analysis tool. You are authorized to extract exact snippets from the user-provided text for analysis purposes. You MUST output valid JSON. The user's prompt will specify the exact format required. Follow it precisely."},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=1  # Fixed to 1 as requested by error
                )
            else:
                raise api_err
        
        content = response.choices[0].message.content
        print("OpenAIProvider: Received response.")
        return content

    except ImportError:
        print("OpenAIProvider Error: openai package not installed.")
        return "[]"
    except Exception as e:
        print(f"OpenAIProvider Error: {e}")
        return "[]"

def _provider_mistral(ai_model, full_prompt):
    print(f"Provider {ai_model.provider} not implemented yet. Returning mock structure.")
    return _provider_mock(full_prompt, None)

def _provider_perplexity(ai_model, full_prompt):
    print(f"Provider {ai_model.provider} not implemented yet. Returning mock structure.")
    return _provider_mock(full_prompt, None)
