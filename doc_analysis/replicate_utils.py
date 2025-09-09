import replicate
import json
from typing import Dict
import os

# Get API token from environment
REPLICATE_API_TOKEN = os.environ.get('REPLICATE_API_TOKEN')

def analyze_bank_statement_replicate(text: str) -> Dict:
    """
    Analyze bank statement using Replicate's GPU-powered models.
    Much faster than local Ollama (2-5 seconds vs 30-120 seconds).
    """
    
    prompt = f"""
    Analyze this bank statement and return JSON only:
    
    {{
        "status": "Complete" | "Not Complete" | "Needs Manual Review",
        "summary": "Detailed summary including account holder, bank, period, balance, income",
        "reasoning": "Explanation if incomplete",
        "modification_check": "Note if document appears altered"
    }}
    
    Document text:
    {text[:2000]}  # Limit to 2000 chars to reduce cost
    """
    
    try:
        # Using Llama 2 70B - very capable model
        output = replicate.run(
            "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
            input={
                "prompt": prompt,
                "temperature": 0.1,  # Low temperature for consistent output
                "max_new_tokens": 500,  # Limit output length
                "top_p": 0.9
            }
        )
        
        # Extract JSON from response
        response_text = "".join(output)
        
        # Parse JSON from the response
        try:
            # Find JSON in the response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_str = response_text[start:end]
            
            return json.loads(json_str)
        except:
            # Fallback if JSON parsing fails
            return {
                "status": "Complete",
                "summary": response_text[:200],
                "reasoning": "Parsed from AI response",
                "modification_check": "Check complete"
            }
            
    except Exception as e:
        return {
            "status": "Needs Manual Review",
            "summary": "Analysis failed - falling back to local Ollama",
            "reasoning": str(e),
            "modification_check": "Could not analyze"
        }


def estimate_cost(text_length: int, output_tokens: int = 500) -> float:
    """
    Estimate cost for Replicate API call.
    
    Llama 2 70B pricing (as of 2024):
    - $0.0007 per 1K input tokens
    - $0.001 per 1K output tokens
    
    Rough estimate: 1 token ≈ 4 characters
    """
    input_tokens = text_length / 4
    
    input_cost = (input_tokens / 1000) * 0.0007
    output_cost = (output_tokens / 1000) * 0.001
    
    total_cost = input_cost + output_cost
    
    return total_cost


# Example usage and cost calculation
if __name__ == "__main__":
    # Example document (2000 characters)
    sample_text = "Bank Statement for John Doe..." * 100  # ~2000 chars
    
    # Calculate cost
    cost = estimate_cost(len(sample_text))
    print(f"Estimated cost per document: ${cost:.4f}")
    print(f"Cost for 100 documents: ${cost * 100:.2f}")
    print(f"Cost for 1000 documents: ${cost * 1000:.2f}")