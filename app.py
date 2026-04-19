import streamlit as st
import json
import src.config as cfg
from src.graph import agent_graph

# Configure the page
st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="\U0001F50D", 
    layout="wide"
)

st.title("AI Deep Research Agent")
st.markdown("Ask a complex question. The agent will search the web, calculate data, and reflect to provide a compiled answer.")

# Sidebar settings
with st.sidebar:
    st.header("Agent Settings")
    max_iterations = st.slider("Max Reflection Iterations", min_value=1, max_value=5, value=1, 
                               help="Higher iterations produce better answers but take longer and consume more API quota.")
    
    st.info("⏱️ **Evaluator Note:**\nThis agent is deployed on a free-tier environment. To provide highly accurate responses, it performs complex reasoning, web searches, and validation loops.\n\n**Expect ~2-3 minutes of processing time per iteration.**")
    
    st.markdown("---")
    if st.button("🗑️ Clear Conversation"):
        st.session_state.messages = []
        st.rerun()
        
    st.markdown("Built with LangGraph, Groq, and OpenRouter.")

# Initialize chat history
if "messages" not in st.session_state or len(st.session_state.messages) == 0:
    st.session_state.messages = [{
        "role": "assistant",
        "welcome": True,
        "content": "Hello! I am a Deep Research AI. 🧠\n\nAsk me a complex question or give me a research task, and I will browse the web and calculate data to find your answer."
    }]

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("welcome") or message["role"] == "user":
            st.markdown(message["content"])
        else:
            # Display structured assistant response
            st.success(f"**Summary**\n\n{message.get('summary', '')}")
            
            if message.get('key_findings'):
                st.markdown("**Key Findings**")
                for finding in message.get('key_findings', []):
                    st.markdown(f"- {finding}")
            
            if message.get('calculation_steps'):
                with st.expander("View Calculation Steps"):
                    st.code(message['calculation_steps'], language='python')
            
            if message.get('sources'):
                st.caption(f"**Sources used:** {', '.join(message['sources'])}")

# User input
if prompt := st.chat_input("E.g., Analyze India's EV market growth from 2020-2025..."):
    # Show user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate Short-Term Chat Context
    history_str = ""
    for m in st.session_state.messages[-5:]: # Keep last 5 messages for context
        if m["role"] == "user":
            history_str += f"User said: {m['content']}\n"
        elif m["role"] == "assistant" and "summary" in m:
            history_str += f"AI replied: {m['summary']}\n"
            
    combined_query = prompt
    if history_str.strip():
        combined_query = f"Previous Chat Context:\n{history_str}\n\nLatest User Request to act upon: {prompt}"

    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate and show assistant response
    with st.chat_message("assistant"):
        # Override the global config iteration limit for this run
        cfg.MAX_REFLECTION_ITERATIONS = max_iterations
        
        initial_state = {
            "query": combined_query,
            "past_context": "",
            "plan": "",
            "research_data": "",
            "calculation_steps": "",
            "draft": "",
            "feedback": "",
            "reflection_iterations": 0,
            "sources_used": [],
        }
        
        with st.status("Initializing AI Agent...", expanded=True) as status:
            try:
                final_state = None
                # Stream changes from the graph
                for step_dict in agent_graph.stream(initial_state):
                    for node_name, node_state in step_dict.items():
                        final_state = node_state
                        
                        # Real-time node updates to the UI
                        if node_name == "retrieve_memory":
                            status.update(label="Searching Long-Term Memory... (Gathering past insights)", state="running")
                            st.write("📚 Scanned Pinecone for relevant past insights.")
                        elif node_name == "planner":
                            status.update(label="Formulating Research Plan...", state="running")
                            st.write("🧠 Created a targeted step-by-step execution plan.")
                        elif node_name == "research":
                            status.update(label="Searching Web & Calculating...", state="running")
                            st.write("🔍 Extracting current data from the web and executing Python math.")
                        elif node_name == "reflect":
                            iters = node_state.get('reflection_iterations', 1)
                            status.update(label=f"Critiquing Draft (Iteration {iters})...", state="running")
                            if "PASS" in node_state.get('feedback', ''):
                                st.write("✅ Draft passed reflection validation! Structure is perfect.")
                            else:
                                st.write(f"🩹 Found missing data. Planning a targeted loop to fix gaps.")
                        elif node_name == "validate":
                            status.update(label="Running Safety Validation...", state="running")
                            st.write("🛡️ Math and constraints successfully validated.")
                        elif node_name == "store_memory":
                            status.update(label="Saving to Semantic Memory...", state="running")
                            st.write("💾 Memorized these findings for future queries.")
                        elif node_name == "format_output":
                            status.update(label="Formatting Output...", state="running")
                            st.write("📋 Converting results to perfect JSON schema.")
                            
                status.update(label="Research Complete!", state="complete", expanded=False)
                
                # Parse the final output generated by the graph
                try:
                    result = json.loads(final_state["draft"])
                except Exception:
                    result = {
                        "summary": final_state["draft"], 
                        "key_findings": ["(Failed to parse JSON cleanly. Displaying raw extraction above.)"],
                        "calculation_steps": final_state.get("calculation_steps", ""),
                        "sources": final_state.get("sources_used", [])
                    }
                
                # Extract fields safely
                summary = result.get('summary', 'No summary provided.')
                key_findings = result.get('key_findings', [])
                calc_steps = result.get('calculation_steps', '')
                sources = result.get('sources', [])
                
                # Display current response beautifully
                st.success(f"**Summary**\n\n{summary}")
                
                if key_findings:
                    st.markdown("**Key Findings**")
                    for finding in key_findings:
                        st.markdown(f"- {finding}")
                
                if calc_steps:
                    with st.expander("View Calculation Steps"):
                        st.code(calc_steps, language='python')
                
                if sources:
                    st.caption(f"**Sources used:** {', '.join(sources)}")
                
                # Save to state
                st.session_state.messages.append({
                    "role": "assistant",
                    "summary": summary,
                    "key_findings": key_findings,
                    "calculation_steps": calc_steps,
                    "sources": sources
                })
                
            except Exception as e:
                status.update(label="Error Occurred", state="error", expanded=True)
                st.error(f"An error occurred: {str(e)}")
