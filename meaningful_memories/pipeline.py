import argparse
import logging
import os

from meaningful_memories.extracter import (
    EntityExtracter,
    LLMLocationExtracter,
    LLMTopicExtracter,
)
from meaningful_memories.interview import Interview
from meaningful_memories.transcriber import WhisperTranscriber, WhisperXTranscriber
from meaningful_memories.utils import read_json
from meaningful_memories.transcript import Transcript

logging.basicConfig(level=logging.INFO)


def process_interview_sample(args):
    interview = Interview(
        args.input_dir, skip_convert=args.skip_convert or args.post_process_only
    )
    if not args.post_process_only:
        if not args.skip_transcribe:
            # transcriber = WhisperTranscriber()
            # transcriber.transcribe(interview)
            transcriber = WhisperXTranscriber()
            transcriber.transcribe(interview)

        if not args.skip_extract:
            extracter = EntityExtracter()
            extracter.extract(interview)
            if args.include_llm_topics:
                topic_extracter = LLMTopicExtracter()
                topic_extracter.extract(interview)
                topic_extracter.aggregate_topics(interview)
                location_extracter = LLMLocationExtracter()
                location_extracter.extract(interview)
        interview.combine_chunks()
        interview.visualize()
        interview.write_to_file()
    else:
        interview.load_from_file()
        interview.visualize()


def process_interview_batch(args, interviews):
    if not args.skip_transcribe:
        # transcriber = WhisperTranscriber()
        # for interview in interviews:
        #     transcriber.transcribe(interview)
        transcriber = WhisperXTranscriber()
        for interview in interviews:
            transcriber.transcribe(interview)

    if not args.skip_extract:
        extracter = EntityExtracter()
        if args.include_llm_topics:
            topic_extracter = LLMTopicExtracter()
            location_extracter = LLMLocationExtracter()
        for interview in interviews:
            extracter.extract(interview)
            if args.include_llm_topics:
                topic_extracter.extract(interview)
                topic_extracter.aggregate_topics(interview)
                location_extracter.extract(interview)

    if not args.post_process_only:
        for interview in interviews:
            interview.combine_chunks()
            interview.visualize()
            interview.write_to_file()
    else:
        for interview in interviews:
            interview.load_from_file()
            interview.visualize()


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline for running transcription and entity extraction. "
    )
    parser.add_argument(
        "-c",
        "--skip-convert",
        action="store_true",
        help="Skip converting video (MP4) to audio (WAV-file already exists).",
    )
    parser.add_argument("--skip-transcribe", action="store_true")
    parser.add_argument(
        "-e",
        "--skip-extract",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        "--include-llm-topics",
        action="store_true",
    )
    parser.add_argument(
        "-p",
        "--post-process-only",
        action="store_true",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("-b", "--batch-upload", action="store_true")
    parser.add_argument("-t", "--text-only", action="store_true")
    parser.add_argument("-w", "--generate-w3", action="store_true")
    parser.add_argument(
        "-d", "--input-dir", help="Path to folder containing input data."
    )
    # parser.add_argument("-o", "--output_dir", help="Path to destination folder.")

    args = parser.parse_args()

    if args.text_only:
        logging.info(f"Running text processing on {args.input_dir}...")
        raw_interviews = read_json(args.input_dir)
        interviews = []
        for raw_interview in raw_interviews:
            headline_filename = "_".join(raw_interview["headline"].split())
            interview_path = os.path.join(
                os.path.dirname(args.input_dir), headline_filename
            )
            if not os.path.exists(interview_path):
                os.mkdir(interview_path)
            interview = Interview(
                interview_path,
                skip_convert=True,
                original_uri=raw_interview["original_uri"],
                interview_label=headline_filename,
            )
            interview.transcript = Transcript(raw_interview["text"])
            interviews.append(interview)
        process_interview_batch(args, interviews)
    else:
        if args.batch_upload:
            logging.info(f"Running batch processing on {args.input_dir}...")
            interviews = []
            for dir in os.listdir(args.input_dir):
                logging.info(f"Running pipeline for {dir}")
                interviews.append(
                    Interview(
                        os.path.join(args.input_dir, dir),
                        skip_convert=args.skip_convert,
                    )
                )
            process_interview_batch(args, interviews)
        else:
            process_interview_sample(args)


if __name__ == "__main__":
    main()
