#!/bin/bash

# --- Script Configuration ---
PROVIDER="google_vertex_ai"
INPUT_BUCKET="llm-batch-api-benchmark-input-bucket"
OUTPUT_BUCKET="llm-batch-api-benchmark-output-bucket"
# Prefix for the state files created by the first command
REPORT_PREFIX="google_vertex_ai_job_reports"
INTERVAL=30 # Check interval in seconds

echo "--- 1. Starting Vertex AI Batch Job Creation ---"
# Execute the initial command to create the batch job
python main.py \
    --provider $PROVIDER \
    --action create_jobs \
    --task text-generation \
    --num_jobs 1 \
    --requests_per_job 10000 \
    --vertex_ai_gcs_input_bucket_name="$INPUT_BUCKET" \
    --vertex_ai_gcs_output_bucket_name="$OUTPUT_BUCKET"

# Check if the job creation command was successful
if [ $? -ne 0 ]; then
    echo "ERROR: Job creation failed (python exited with non-zero status). Exiting."
    exit 1
fi

echo "Job creation command completed. State file should now exist."
echo "Starting continuous monitoring loop (checking every ${INTERVAL}s). Press Ctrl+C to stop."
echo "Waiting 5 seconds for the first state file to be written..."
sleep 5 # Give a moment for the initial command to write its state file

# --- 2. Continuous Job Status Check Loop ---
while true; do
    echo "--------------------------------------------------------"
    echo "Attempting to find the latest state file..."
    
    # Use ls -t to list matching files sorted by modification time (newest first).
    # head -n 1 takes the newest file.
    # 2>/dev/null suppresses "No such file or directory" errors if no file exists yet.
    latest_file=$(ls -t ${REPORT_PREFIX}* 2>/dev/null | head -n 1)

    if [ -z "$latest_file" ]; then
        echo "WARNING: No state file found with prefix '${REPORT_PREFIX}'. Retrying in ${INTERVAL} seconds."
    else
        echo "Found latest state file: ${latest_file}"
        
        # --- NEW LOGIC: Check if the file is empty ---
        if [ -s "$latest_file" ]; then
            # File is NOT empty (-s checks if file has a size greater than zero)
            
            # Run the job check command using the found file name
            echo "Running job status check for $latest_file..."
            python main.py \
                --provider $PROVIDER \
                --action check_jobs_from_file \
                --vertex_ai_gcs_input_bucket_name="$INPUT_BUCKET" \
                --vertex_ai_gcs_output_bucket_name="$OUTPUT_BUCKET" \
                --state_file "$latest_file"
                
            # Note: The 'check_jobs_from_file' script must be responsible for
            # emptying the file once all jobs are complete for the exit logic to work.
            
        else
            # File IS empty
            echo "SUCCESS: Latest state file (${latest_file}) is empty. All jobs are determined to be complete."
            echo "Exiting continuous monitoring loop."
            break # Exit the while loop
        fi
    fi

    echo "Status check complete. Waiting ${INTERVAL} seconds before next check..."
    sleep $INTERVAL
done

echo "Script finished."