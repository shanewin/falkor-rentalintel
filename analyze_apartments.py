import pandas as pd
import matplotlib.pyplot as plt

# Define file path (relative to the project root)
file_path = "data/Apartments_from_search.tsv"

# Load the TSV file
df = pd.read_csv(file_path, sep="\t")

# Display first few rows
print("\nFirst few rows of the dataset:")
print(df.head())

# Get basic info
print("\nDataset Info:")
print(df.info())

# Get summary statistics
print("\nSummary Statistics:")
print(df.describe())

# Check for missing values
print("\nMissing Values:")
print(df.isnull().sum())

# Plot Rent Price Distribution
plt.figure(figsize=(10,5))
df['rent_price'].hist(bins=20)
plt.title('Rent Price Distribution')
plt.xlabel('Rent Price ($)')
plt.ylabel('Number of Listings')
plt.savefig("rent_price_distribution.png")  # Save plot as an image
print("\nSaved rent price distribution as 'rent_price_distribution.png'")

# Plot Most Common Neighborhoods
df['neighborhood'].value_counts().head(10).plot(kind='bar', figsize=(10,5), title="Top 10 Neighborhoods")
plt.xlabel('Neighborhood')
plt.ylabel('Number of Listings')
plt.savefig("top_neighborhoods.png")
print("\nSaved top neighborhoods chart as 'top_neighborhoods.png'")

print("\nAnalysis complete. Check the generated charts.")
