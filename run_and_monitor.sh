#!/bin/bash

# Usage: bash ./run_and_monitor.sh --provider {provider} --task {task} --num_jobs {num_jobs} --requests_per_job {requests_per_job} --input_bucket {input_bucket} --output_bucket {output_bucket} --interval {interval}

# --- Script Configuration (Defaults) ---
# These values will be used unless overridden by command-line arguments
PROVIDER="google_vertex_ai"
INPUT_BUCKET="llm-batch-api-benchmark-input-bucket"
OUTPUT_BUCKET="llm-batch-api-benchmark-output-bucket"
INTERVAL=30 # Check interval in seconds
TASK="text-generation" # Change to embedding or other task as needed
NUM_JOBS=1 # Number of jobs to create
REQUESTS_PER_JOB=200 # Number of requests per job
# REPORT_PREFIX will be set after parsing, based on the final PROVIDER value

# --- Argument Parsing Loop ---
# This loop reads arguments (e.g., --provider "value") and overwrites defaults.
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --provider)
        PROVIDER="$2"
        shift 2 # past argument and value
        ;;
        --input_bucket)
        INPUT_BUCKET="$2"
        shift 2
        ;;
        --output_bucket)
        OUTPUT_BUCKET="$2"
        shift 2
        ;;
        --interval)
        INTERVAL="$2"
        shift 2
        ;;
        --task)
        TASK="$2"
        shift 2
        ;;
        --num_jobs)
        NUM_JOBS="$2"
        shift 2
        ;;
        --requests_per_job)
        REQUESTS_PER_JOB="$2"
        shift 2
        ;;
        *)
        # unknown option
        echo "ERROR: Unknown option: $1"
        echo "Usage: $0 [--provider <val>] [--input_bucket <val>] [--output_bucket <val>] [--interval <val>] [--task <val>] [--num_jobs <val>] [--requests_per_job <val>]"
        exit 1
        ;;
    esac
done


REPORT_PREFIX="${PROVIDER}_job_reports"


# --- Print Final Configuration ---
echo "--- 🚀 Starting Batch Job with Configuration ---"
echo "Provider:         $PROVIDER"
echo "Task:             $TASK"
echo "Input Bucket:     $INPUT_BUCKET"
echo "Output Bucket:    $OUTPUT_BUCKET"
echo "Report Prefix:    $REPORT_PREFIX"
echo "Check Interval:   ${INTERVAL}s"
echo "Jobs to Create:   $NUM_JOBS"
echo "Requests per Job: $REQUESTS_PER_JOB"
echo "-------------------------------------------------"

# --- 1. Starting Batch Job Creation ---
echo "Starting job creation..."
python main.py \
    --provider $PROVIDER \
    --action create_jobs \
    --task $TASK \
    --num_jobs $NUM_JOBS \
    --requests_per_job $REQUESTS_PER_JOB \
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