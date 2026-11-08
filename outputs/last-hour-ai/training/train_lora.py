"""Validate a reviewed dataset; train only with --run on an explicitly chosen GPU."""
import argparse
import json
from pathlib import Path


def read_rows(path):
    rows = []
    for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {'prompt', 'completion'} or not isinstance(row['prompt'], list) or not row['prompt']:
            raise ValueError(f'Invalid prompt/completion at line {line_no}')
        for message in row['prompt']:
            if message.get('role') not in {'system', 'user', 'assistant'} or not isinstance(message.get('content'), str):
                raise ValueError(f'Invalid prompt message at line {line_no}')
        if len(row['completion']) != 1 or row['completion'][0].get('role') != 'assistant':
            raise ValueError(f'Invalid completion at line {line_no}')
        target = json.loads(row['completion'][0]['content'])
        if set(target) != {'content', 'question', 'answer'} or not all(isinstance(v, str) for v in target.values()):
            raise ValueError(f'Invalid tutor target at line {line_no}')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--train-file', required=True)
    parser.add_argument('--validation-file', required=True)
    parser.add_argument('--output', default='./adapters/study-tutor')
    parser.add_argument('--base-model', default='Qwen/Qwen3-4B-Instruct-2507')
    parser.add_argument('--max-length', type=int, default=4096)
    parser.add_argument('--epochs', type=float, default=1)
    parser.add_argument('--run', action='store_true', help='Explicitly start GPU training; otherwise validate only')
    args = parser.parse_args()
    train, validation = read_rows(args.train_file), read_rows(args.validation_file)
    print(json.dumps({'train':len(train), 'validation':len(validation), 'will_train':args.run}))
    if not args.run:
        return
    if not train or not validation:
        raise ValueError('Reviewed train and held-out validation examples are both required')
    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose an empty output directory; existing adapters will not be overwritten')
    import torch
    from datasets import Dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU required for this QLoRA recipe')
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    def fits(row):
        return len(tokenizer.apply_chat_template(row['prompt'] + row['completion'], tokenize=True)) <= args.max_length
    train = [row for row in train if fits(row)]
    validation = [row for row in validation if fits(row)]
    if not train or not validation:
        raise ValueError('All examples exceeded max length; shorten the reviewed material instead of truncating targets')
    model = AutoModelForCausalLM.from_pretrained(args.base_model,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype), device_map={'':0})
    model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    trainer = SFTTrainer(model=model, processing_class=tokenizer,
        train_dataset=Dataset.from_list(train), eval_dataset=Dataset.from_list(validation),
        peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias='none',
                              target_modules='all-linear', task_type='CAUSAL_LM'),
        args=SFTConfig(output_dir=str(output), max_length=args.max_length, packing=False,
            completion_only_loss=True, num_train_epochs=args.epochs, per_device_train_batch_size=1,
            per_device_eval_batch_size=1, gradient_accumulation_steps=8, learning_rate=1e-4,
            bf16=bf16, fp16=not bf16, gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant':False}, eval_strategy='epoch',
            save_strategy='epoch', logging_steps=5, report_to='none', seed=42))
    trainer.train()
    trainer.save_model(str(output))
    tokenizer.save_pretrained(str(output))
    (output/'training-summary.json').write_text(json.dumps({'base_model':args.base_model,
        'train_rows':len(train),'validation_rows':len(validation),'weights_trained':True},indent=2))


if __name__ == '__main__':
    main()
