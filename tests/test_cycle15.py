"""Cycle 15 — real LLM agent runtime (provider subprocess+JSON loop)."""




def _env(tmp_path, monkeypatch, provider_text):
    monkeypatch.setenv("PRODUCT_FORGE_HOME", str(tmp_path / "pf"))
    from product_forge.config import db_path, home_dir, load_config
    from product_forge.domain.models import Product
    from product_forge.store.sqlite import Store

    home = home_dir("user")
    (home / "state" / "objects").mkdir(parents=True, exist_ok=True)
    cfg = load_config(home)
    if provider_text is not None:
        prov = tmp_path / "provider.py"
        prov.write_text(provider_text)
        cfg["gateway"] = {"provider_cmd": ["python3", str(prov)], "timeout_s": 15}
    st = Store(db_path(home, cfg))
    st.put("products", Product(id="p1", workspace_id="w1", name="Pay"))
    return st, cfg


def _agent():
    from product_forge.domain.models import AgentDefinition
    return AgentDefinition(id="a1", product_id="p1", name="Analyst",
                           template="product-analyst", mission="ground answers",
                           tools_allowed=["knowledge_query"], status="published")


def test_llm_run_tool_call_then_answer(tmp_path, monkeypatch):
    provider = (
        "import json,sys\n"
        "req=json.loads(sys.stdin.read())\n"
        "hist=[m for m in req['history'] if m.get('role')=='tool']\n"
        "if not hist:\n"
        " print(json.dumps({'tool_calls':[{'tool':'knowledge_query','arguments':{'question':'E42'}}],"
        "  'tokens_in':10,'tokens_out':5}))\n"
        "else:\n"
        " print(json.dumps({'text':'E42 means insufficient funds [cited]',"
        "  'tokens_in':40,'tokens_out':20}))\n")
    st, cfg = _env(tmp_path, monkeypatch, provider)
    agent = _agent()
    st.put("agents", agent)
    from product_forge.agents.runtime import run_agent

    run = run_agent(st, agent, "what is E42?", cfg=cfg)
    assert run["status"] == "completed"
    assert run["output"]["llm"] is True
    assert "insufficient funds" in run["output"]["answer"]
    kinds = [s["step"] for s in run["steps"]]
    assert "llm-turn-0" in kinds and "knowledge_query" in kinds
    st.close()


def test_llm_tool_denied_by_policy(tmp_path, monkeypatch):
    provider = (
        "import json,sys\n"
        "req=json.loads(sys.stdin.read())\n"
        "print(json.dumps({'tool_calls':[{'tool':'delegate_exec','arguments':{}}],"
        "'tokens_in':5,'tokens_out':2}))\n")
    st, cfg = _env(tmp_path, monkeypatch, provider)
    agent = _agent()  # tools_allowed only knowledge_query
    st.put("agents", agent)
    from product_forge.agents.runtime import run_agent

    run = run_agent(st, agent, "do something", cfg=cfg)
    denied = [s for s in run["steps"] if s.get("status") == "denied"]
    assert denied  # undeclared tool blocked by policy, not executed
    st.close()


def test_no_provider_falls_back_deterministic(tmp_path, monkeypatch):
    st, cfg = _env(tmp_path, monkeypatch, None)
    agent = _agent()
    st.put("agents", agent)
    from product_forge.agents.runtime import run_agent

    run = run_agent(st, agent, "hello", cfg=cfg)
    assert run["status"] in {"completed", "partial"}
    assert run["output"].get("llm") is not True
    st.close()


def test_llm_max_turns_honest_stop(tmp_path, monkeypatch):
    provider = (
        "import json,sys\n"
        "json.loads(sys.stdin.read())\n"
        "print(json.dumps({'tool_calls':[{'tool':'knowledge_query','arguments':{}}],"
        "'tokens_in':1,'tokens_out':1}))\n")
    st, cfg = _env(tmp_path, monkeypatch, provider)
    agent = _agent()
    st.put("agents", agent)
    from product_forge.agents.runtime import run_agent

    run = run_agent(st, agent, "loop forever", cfg=cfg)
    assert run["status"] == "partial"
    assert "max turns" in run["output"]["refusal"]
    st.close()
