import random
from datetime import datetime, timedelta
import os

def generate_large_input_file(filename, target_size_gb=1.5):
    # Define possible values
    package_sizes = ['S', 'M', 'L']
    carriers = ['MR', 'LP']
    
    # Convert target size to bytes
    target_size_bytes = target_size_gb * 1024 * 1024 * 1024
    
    # Start date (January 1, 2015)
    start_date = datetime(2015, 1, 1)
    
    # Open file for writing
    with open(filename, 'w') as f:
        current_size = 0
        
        # Keep writing until we reach the target file size
        while current_size < target_size_bytes:
            # Generate a batch of entries to improve performance
            batch = []
            
            for _ in range(10000):  # Write in batches of 10,000 entries
                # Generate a random date within a 3-year period
                random_days = random.randint(0, 365 * 3)  # Up to 3 years
                current_date = start_date + timedelta(days=random_days)
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Occasionally generate an invalid entry (1% chance)
                if random.random() < 0.01:
                    invalid_entries = [
                        f"{date_str} CUSPS",
                        f"{date_str} X LP",
                        f"{date_str} S XX",
                        f"{date_str} S",
                        f"invalid-date S MR"
                    ]
                    batch.append(random.choice(invalid_entries))
                else:
                    # Generate a valid entry
                    package_size = random.choice(package_sizes)
                    carrier = random.choice(carriers)
                    batch.append(f"{date_str} {package_size} {carrier}")
            
            # Join batch with newlines and write to file
            batch_text = '\n'.join(batch) + '\n'
            f.write(batch_text)
            
            # Update current size
            current_size = os.path.getsize(filename)
            
            # Print progress
            print(f"Generated {current_size / (1024 * 1024 * 1024):.2f} GB", end='\r')
        
        print(f"\nCompleted! Generated file size: {current_size / (1024 * 1024 * 1024):.2f} GB")

if __name__ == "__main__":
    generate_large_input_file("input.txt")
    print("File generation complete!")