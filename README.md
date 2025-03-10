# Shipping Discount Calculator

A high-performance, memory-efficient command-line tool for calculating shipping discounts based on defined rules. This solution processes large data files in parallel while maintaining state across transactions.

## Features

- **High Performance**: Processes large files (1.5GB+) efficiently using parallel processing
- **Memory Efficient**: Streams data in chunks to avoid loading the entire file into memory
- **Extendable Rules**: Flexible design to easily add or modify discount rules
- **Beautiful UI**: Clean terminal interface with progress tracking and statistics
- **Detailed Reporting**: Comprehensive statistics about processed transactions

## Usage

python shipping_discount_calculator.py [input_file] [output_file] [options]

### Arguments

- `input_file`: Path to the input file (default: "input.txt")
- `output_file`: Path to save the output (optional, outputs to console if not provided)

### Options

- `--processes` or `-p`: Number of processes to use (default: 4 or CPU count, whichever is lower)
- `--quiet` or `-q`: Suppress transaction output and only show summary

### Examples

Process the default input file and display results to console:

python shipping_discount_calculator.py

Process a specific input file and save results to an output file:

python shipping_discount_calculator.py large_data.txt results.txt

Use a specific number of processing cores:

python shipping_discount_calculator.py input.txt output.txt -p 2

## Test Data Generation

The repository includes a script to generate test data for benchmarking:

python create_shipping_data.py

This will create a 1.5GB `input.txt` file with random shipping transactions to test the calculator.

**WARNING**: Running this script requires significant disk space for the output file.

## Memory Usage Considerations

While the calculator is designed to be memory-efficient for processing, increasing the number of parallel processes will increase memory usage. For maximum performance:

- **High Memory Mode**: Using more processes (e.g., `-p 8` or higher) will significantly speed up processing but requires more RAM
- **Low Memory Mode**: Using fewer processes (e.g., `-p 2`) reduces memory usage but increases processing time

For the fastest performance on large files, ensure your system has at least 8GB of free RAM. The memory requirements scale with both file size and process count.

## Implementation Details

### Discount Rules

The calculator implements the following discount rules:

1. **Small Package Rule**: All S shipments match the lowest S package price among providers
2. **Third LP Large Package Rule**: The third L shipment via LP in a calendar month is free
3. **Monthly Discount Cap**: Total discounts cannot exceed 10€ per calendar month

### Performance Optimizations

- **Multiprocessing**: Splits the file into chunks and processes them in parallel
- **Memory Mapping**: Efficiently reads file chunks without loading everything into memory
- **Thread-Safe Progress**: Uses locks to ensure accurate progress tracking across processes
- **Optimized Data Structures**: Fast lookups with sets and pre-calculated values

## Input Format

Each line in the input file should contain:

- Date (ISO format YYYY-MM-DD)
- Package size code (S, M, or L)
- Carrier code (LP or MR)

Example:

2015-02-01 S MR
2015-02-03 L LP
2015-02-05 S LP

## Output Format

Each line of output includes:

- The original input line
- The final shipping price after discount
- The discount amount (or "-" if no discount)

Example:

2015-02-01 S MR 1.50 0.50
2015-02-03 L LP 6.90 -
2015-02-05 S LP 1.50 -

## Architecture

The solution follows a modular design with the following components:

1. **ShippingCalculator**: Core business logic for calculating discounts
2. **Process Management**: Efficient parallel processing of file chunks
3. **Progress Tracking**: Real-time progress visualization
4. **Statistics Reporting**: Detailed summary of processing results

## Extending the Code

### Adding New Rules

To add a new discount rule:

1. Implement the rule as a method in the `ShippingCalculator` class
2. Modify the `calculate_discount` method to include your new rule
3. Ensure proper state tracking for your rule (if required)

### Performance Tuning

- Adjust chunk size by modifying the division logic in `process_file_parallel`
- Change the default process count by modifying the `min(4, mp.cpu_count())` line
- For very large files, consider further optimizations to the file reading mechanism

## Testing

This solution has been tested with files up to 1.5GB in size, processing millions of transactions efficiently. The parallel processing approach ensures good performance scaling with available CPU cores.
