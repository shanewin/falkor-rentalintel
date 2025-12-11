# Cost calculation for Replicate document analysis

# Typical bank statement analysis
input_chars = 2000  # Limited text we send
output_chars = 500  # JSON response

# Convert to tokens (roughly 1 token = 4 characters)
input_tokens = input_chars / 4  # 500 tokens
output_tokens = output_chars / 4  # 125 tokens

# Llama 2 70B pricing on Replicate
input_cost_per_1k = 0.0007
output_cost_per_1k = 0.001

# Calculate costs
input_cost = (input_tokens / 1000) * input_cost_per_1k
output_cost = (output_tokens / 1000) * output_cost_per_1k
total_per_doc = input_cost + output_cost

print('🔍 PER DOCUMENT ANALYSIS:')
print(f'Input cost: ${input_cost:.5f}')
print(f'Output cost: ${output_cost:.5f}')
print(f'Total per document: ${total_per_doc:.5f}')
print()
print('📊 VOLUME PRICING:')
print(f'100 documents/month: ${total_per_doc * 100:.2f}')
print(f'1,000 documents/month: ${total_per_doc * 1000:.2f}')
print(f'10,000 documents/month: ${total_per_doc * 10000:.2f}')
print()
print('⚡ SPEED COMPARISON:')
print('Ollama (CPU): 30-120 seconds')
print('Replicate (GPU): 2-5 seconds')
print('Speed improvement: 10-40x faster!')