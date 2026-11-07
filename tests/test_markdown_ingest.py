from product_forge.knowledge.ingest import chunk_markdown, sha256_text


def test_markdown_chunks_preserve_heading_path_and_spans() -> None:
    source = "# Runbook\n\n## Deploy\n\nUse the release command.\n"
    chunks = chunk_markdown(source)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.heading_path == ("Runbook", "Deploy")
    assert source[chunk.start_offset:chunk.end_offset] == chunk.text
    assert chunk.content_hash == sha256_text(chunk.text)
    assert chunk.sequence == 0


def test_markdown_chunks_keep_fenced_code_atomic() -> None:
    source = "```python\n" + ("print('x')\n" * 500) + "```\n"
    chunks = chunk_markdown(source, target=30, max_len=40)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("```python")
    assert chunks[0].text.endswith("```")


def test_markdown_chunks_keep_table_atomic() -> None:
    source = "| name | value |\n| --- | --- |\n| one | two |\n"
    chunks = chunk_markdown(source, target=5, max_len=8)
    assert len(chunks) == 1
    assert chunks[0].text.count("|") >= 6

