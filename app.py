import streamlit as st
from src.graph import run_agent

# Configure the page
st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AI Deep Research Agent")
st.markdown("Ask a complex question. The agent will search the web, calculate data, and reflect to provide a compiled answer.")

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Agent Settings")
    max_iterations = st.slider("Max Reflection Iterations", min_value=1, max_value=5, value=2, 
                               help="Higher iterations produce better answers but take longer and consume more API quota.")
    st.markdown("---")
    st.markdown("Built with LangGraph, Groq, and OpenRouter.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            # Display structured assistant response
            st.markdown(f"### Summary\n{message['summary']}")
            
            st.markdown("### Key Findings")
            for finding in message.get('key_findings', []):
                st.markdown(f"- {finding}")
            
            if message.get('calculation_steps'):
                with st.expander("View Calculation Steps"):
                    st.code(message['calculation_steps'], language='python')
            
            if message.get('sources'):
                st.markdown(f"**Sources used:** {', '.join(message['sources'])}")

# User input
if prompt := st.chat_input("E.g., Analyze India's EV market growth from 2020-2025..."):
    # Show user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate and show assistant response
    with st.chat_message("assistant"):
        import json
        import src.config as cfg
        from src.graph import agent_graph
        
        # Override the global config iteration limit for this run
        cfg.MAX_REFLECTION_ITERATIONS = max_iterations
        
        initial_state = {
            "query": prompt,
            "past_context": "",
            "plan": "",
            "research_data": "",
            "calculation_steps": "",
            "draft": "",
            "feedback": "",
            "reflection_iterations": 0,
            "sources_used": [],
        }
        
        with st.status("Agent is booting up...", expanded=True) as status:
            try:
                final_state = None
                # Stream changes from the graph
                for step_dict in agent_graph.stream(initial_state):
                    for node_name, node_state in step_dict.items():
                        final_state = node_state
                        
                        # Real-time node updates to the UI
                        if node_name == "retrieve_memory":
                            status.update(label="Searching memory...", state="running")
                            st.write("📚 Retrieved relevant past insights from Pinecone.")
                        elif node_name == "planner":
                            status.update(label="Formulating research plan...", state="running")
                            st.write("🧠 Structured a targeted execution plan.")
                        elif node_name == "research":
                            status.update(label="Searching & Calculating...", state="running")
                            st.write("🔍 Browsed web and executed Python data extraction calculations.")
                        elif node_name == "reflect":
                            iters = node_state.get('reflection_iterations', 1)
                            status.update(label=f"Reflecting on draft (Iteration {iters})...", state="running")
                            if "PASS" in node_state.get('feedback', ''):
                                st.write("🪞 Draft passed reflection validation!")
                            else:
                                st.write(f"🪞 Found data gaps. Planning a targeted loop to fix them.")
                        elif node_name == "validate":
                            status.update(label="Validating data...", state="running")
                            st.write("✅ Math and logic constraints validated securely.")
                        elif node_name == "store_memory":
                            status.update(label="Saving to Long-Term Memory...", state="running")
                            st.write("💾 Memorized findings for future queries.")
                        elif node_name == "format_output":
                            status.update(label="Formatting structured response...", state="running")
                            st.write("📋 Converting markdown to JSON schema.")
                            
                status.update(label="Research Complete!", state="complete", expanded=False)
                
                # Parse the final output generated by the graph
                try:
                    result = json.loads(final_state["draft"])
                except Exception:
                    result = {
                        "summary": final_state["draft"], 
                        "key_findings": ["(Failed to parse JSON properly, displaying raw format.)"],
                        "calculation_steps": final_state.get("calculation_steps", ""),
                        "sources": final_state.get("sources_used", [])
                    }
                
                # Extract fields safely
                summary = result.get('summary', 'No summary provided.')
                key_findings = result.get('key_findings', [])
                calc_steps = result.get('calculation_steps', '')
                sources = result.get('sources', [])
                
                # Display current response
                st.markdown(f"### Summary\n{summary}")
                
                if key_findings:
                    st.markdown("### Key Findings")
                    for finding in key_findings:
                        st.markdown(f"- {finding}")
                
                if calc_steps:
                    with st.expander("View Calculation Steps"):
                        st.code(calc_steps, language='python')
                
                if sources:
                    st.markdown(f"**Sources used:** {', '.join(sources)}")
                
                # Save to state
                st.session_state.messages.append({
                    "role": "assistant",
                    "summary": summary,
                    "key_findings": key_findings,
                    "calculation_steps": calc_steps,
                    "sources": sources
                })
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
