# ChunkLab 1.0.0

[한국어 README](README.ko.md)

ChunkLab is a local, offline-first Streamlit app for document chunking experiments. It uploads Markdown, HTML, or TXT files from your machine, applies deterministic structural chunking by default, previews provenance, and exports JSONL.

## Quickstart

Clone this repository and install from its source directory:

```sh
git clone https://github.com/0-ki/chunklab.git
cd chunklab
```

Do not run `pip install chunklab`: the name on PyPI belongs to an unrelated project.

Python 3.11 or newer is required. The independently tested release environment was Linux with Python 3.12.

POSIX shell:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
chunklab
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
chunklab
```

For development you can also run:

```bash
streamlit run chunklab/app.py
```

Test and benchmark:

```bash
python -m pytest -q
python -m chunklab.benchmark
```

## Usage

1. Upload a local `.md`, `.markdown`, `.html`, `.htm`, or `.txt` file.
2. Choose a UTF-8 byte hard limit. This is a deterministic byte budget, not a tokenizer/model-token count.
3. Optionally enable deterministic pre-screening, quality audit, or the offline fake boundary comparison.
4. Review chunks, provenance, issues, and any pre-screen decisions.
5. Download JSONL and the issue report.

The installed `chunklab` launcher binds Streamlit to `localhost` and disables Streamlit usage telemetry. It rejects CLI overrides of those protected settings while still allowing port/headless flags.

## Privacy and provider limitations

- Default operation is offline and local; ChunkLab does not fetch URLs and does not call live providers automatically.
- Uploaded text is treated as untrusted evidence. ChunkLab does not give provider adapters tools or control and does not place credentials in request bodies.
- All provider paths are experimental. OpenAI Decisions, OpenAI Chat Completions A/B logprobs, and OpenRouter Jev require explicit provider selection, a button press, and separate live-provider consent in the GUI.
- Provider paths are mock-tested only in this release. No real provider calls were made, and no live provider behavior is claimed verified.
- The OpenAI Decisions and Chat Completions adapters read only `CHUNKLAB_OPENAI_API_KEY`; the OpenRouter Jev adapter reads only `CHUNKLAB_OPENROUTER_API_KEY`.
- The Chat Completions A/B logprobs path accepts only exact one-token `A`/`B` outputs with complete first-token A/B logprob data and labels its score `relative_token_proxy`, not provider correctness probability.
- ChunkLab does not persist uploaded payloads or secrets.

## Offline benchmarks

`python -m chunklab.benchmark` reports the development Korean/English synthetic benchmark and a separate held-out Korean law-paraphrase case. Both use the same deterministic lexical ranker and UTF-8 byte budget per condition. The held-out case is based on paraphrases, is not legal advice, cites the Act and Enforcement Decree sources, and is reported separately so it is not used for tuning.

Measured for v1.0.0: the development benchmark found all expected evidence under budget for all 5 queries in each condition. The held-out benchmark found all 3 required evidence spans in each condition. These small offline fixtures did not establish a split-quality gain from screening or offline mock-guided chunking.

The upstream Jev/RAG research implementation is cited as inspiration for paragraph verification, query scoring, boundary decisions, and tagging. ChunkLab does not claim to reproduce its results or validate live Jev behavior.

## Scope for 1.0.0

Stable: local Markdown/HTML/TXT upload, structural chunking, opt-in deterministic pre-screen/review/restore, opt-in quality audit, provenance preview, JSONL/issue export, offline mock-guided boundary comparison, and package/CLI use outside a checkout.

Experimental: all live-provider paths and provider-derived boundary comparisons. They remain opt-in and mock-tested only.

Excluded: URL fetching, PDF/OCR, deployment, automatic live provider calls, live provider validation, legal advice, and production retrieval-quality claims. Full boundary optimization, delimiter-specific chunking, graph features, hierarchical summaries, vector databases, and retrieval pipeline integrations are deferred.

## License and notices

ChunkLab is released under the MIT License; see [LICENSE](LICENSE). Third-party usage and attribution notices are in [NOTICE.md](NOTICE.md). Release notes are in [RELEASE_NOTES.md](RELEASE_NOTES.md).
