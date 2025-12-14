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
    
    # Main Instructions are in the prompt
    current_prompt = full_prompt_text
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        print(f"Pipeline: Dispatching request (Attempt {retry_count+1}/{max_retries+1})...")
        
        # 2. Dispatch to LLM
        try:
            llm_response_json = dispatch_llm_request(ai_model, current_prompt, page)
        except Exception as e:
            # API Error
            page.status = "error"
            page.error_message = f"API Error: {str(e)}"
            page.save()
            return 0

        # 3. Validation & Parsing
        try:
            # Handle markdown code blocks if present
            cleaned_json = llm_response_json.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = cleaned_json.split("\n", 1)[1]
                if cleaned_json.endswith("```"):
                    cleaned_json = cleaned_json.rsplit("\n", 1)[0]
            
            # Check for Refusal / Text Response appearing as JSON error
            if "Request requires extraction of exact quotes" in cleaned_json or "Contrainte de sécurité" in cleaned_json:
                msg = "LLM Refusal: The model refused to extract quotes due to safety policies. Try using a larger model (GPT-4) or rephrasing the prompt."
                print(f"Pipeline Error: {msg}")
                page.status = "error"
                page.error_message = msg
                page.save()
                return 0

            arguments_data = json.loads(cleaned_json)
            
            # Some providers return {"arguments": [...]} or {"data": [...]} when forced to json_object
            # We look for the first list value
            if isinstance(arguments_data, dict):
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
                    raise ValueError("JSON object did not contain a list of arguments under expected keys.")

            # Use Serializer for Validation
            from .serializers import AnalysisItemSerializer
            serializer = AnalysisItemSerializer(data=arguments_data, many=True)
            
            if not serializer.is_valid():
                # Validation Failed
                error_msg = f"JSON Validation Failed: {serializer.errors}"
                print(f"Pipeline Warning: {error_msg}")
                
                if retry_count < max_retries:
                    # Prepare retry prompt
                    feedback = f"\n\nERREUR DANS LE JSON PRÉCÉDENT :\n{json.dumps(serializer.errors, indent=2)}\n\nCORRIGE LE JSON ET RENVOIE UNIQUEMENT LA LISTE CORRIGÉE."
                    current_prompt += f"\n\n--- RÉPONSE INCORRECTE ---\n{llm_response_json}\n{feedback}"
                    retry_count += 1
                    continue
                else:
                    # Give up
                    page.status = "error"
                    page.error_message = f"Validation failed after retries. Errors: {serializer.errors}"
                    page.save()
                    return 0

            # If Valid, proceed to binding
            validated_data = serializer.validated_data
            created_count = 0
            
            # Clear old data for this page
            page.blocks.all().delete() 
            
            MODE_MAPPING = {
                "A initier": "IN",
                "Discuté": "DC",
                "Disputé": "DP",
                "Controversé": "CT",
                "Consensuel": "CS"
            }
            
            from .models import TextBlock, Argument, Theme

            for item in validated_data:
                quotation = item['text_quote'].strip()
                summary = item['summary']
                hypostasis = item['hypostasis'] # Already lowercased/validated by serializer? Check serializer implementation.
                mode_label = item['mode']
                theme_str = item['theme']
                significant_extract = item['significant_extract']
                
                start_offset = page.text_readability.find(quotation)
                
                if start_offset == -1:
                    print(f"Pipeline Warning: Quote not found in text: '{quotation[:30]}...'")
                    continue
                    
                end_offset = start_offset + len(quotation)
                mode_code = MODE_MAPPING.get(mode_label, "IN")

                # Create TextBlock
                block = TextBlock.objects.create(
                    page=page,
                    selector="body",
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text=quotation,
                    significant_extract=significant_extract,
                    hypostasis=hypostasis,
                    modes=mode_code
                )
                
                # Handle Theme
                if theme_str:
                    theme_obj, _ = Theme.objects.get_or_create(name=theme_str.strip())
                    block.themes.add(theme_obj)
                
                # Create Argument linked to Block
                Argument.objects.create(
                    page=page,
                    text_block=block,
                    selector="body",
                    start_offset=start_offset,
                    end_offset=end_offset,
                    text_original=quotation,
                    summary=summary
                )
                created_count += 1
            
            # Success
            page.status = "completed"
            page.save()
            print(f"Pipeline: Created {created_count} blocks/arguments.")
            return created_count

        except json.JSONDecodeError as e:
            if retry_count < max_retries:
                print(f"Pipeline: JSON Decode Error ({e}). Retrying...")
                feedback = f"\n\nERREUR JSON : {str(e)}\nRENVOIE UN JSON VALIDE."
                current_prompt += f"\n\n--- REPONSE INVALIDE ---\n{llm_response_json}\n{feedback}"
                retry_count += 1
                continue
            else:
                page.status = "error"
                page.error_message = f"JSON Decode Error: {e}"
                page.save()
                return 0
        except ValueError as e: # Catch the custom ValueError for unwrapping
            if retry_count < max_retries:
                print(f"Pipeline: JSON Structure Error ({e}). Retrying...")
                feedback = f"\n\nERREUR DE STRUCTURE JSON : {str(e)}\nRENVOIE UN JSON VALIDE AVEC UNE LISTE D'ARGUMENTS."
                current_prompt += f"\n\n--- REPONSE INVALIDE ---\n{llm_response_json}\n{feedback}"
                retry_count += 1
                continue
            else:
                page.status = "error"
                page.error_message = f"JSON Structure Error: {e}"
                page.save()
                return 0
    
    return 0


def build_full_prompt(page, prompt):
    """
    Concatenates TextInputs and injects Page variables.
    """
    inputs = prompt.inputs.all().order_by('order')
    full_text = ""
    
    for inp in inputs:
        # full_text += f"\n--- {inp.role} ---\n" # Role is for organization, not necessarily prompt text injection
        full_text += inp.content + "\n"
        
    # Variable Injection
    # We replace {{ TEXT }} with the content
    if "{{ TEXT }}" in full_text:
        full_text = full_text.replace("{{ TEXT }}", page.text_readability)
    else:
        # Default append if no tag found
        full_text += "\n\n--- TEXTE À ANALYSER ---\n" + page.text_readability
        
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
    target_count = min(5, len(sentences))
    if target_count == 0:
        return "[]"

    selected_sentences = random.sample(sentences, target_count)
    
    output_data = []
    
    modes_list = ["A initier", "Discuté", "Disputé", "Controversé", "Consensuel"]
    hypostasis_list = ["problème", "principe", "donnée", "valeur", "théorie"]
    
    for sentence in selected_sentences:
        mode = random.choice(modes_list)
        hypostasis = random.choice(hypostasis_list)
        
        # Determine strict summary length
        summary = f"Analyse simulée ({hypostasis}/{mode})."
        sig_extract = sentence[:20] + "..."
        
        output_data.append({
            "text_quote": sentence, # EXACT text for linking
            "summary": summary,
            "hypostasis": hypostasis,
            "mode": mode,
            "significant_extract": sig_extract
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
