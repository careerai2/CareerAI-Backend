# import uuid

# from langchain_anthropic import ChatAnthropic
# from langchain_core.runnables import RunnableConfig

# from langgraph.checkpoint.redis import RedisSaver
# from langgraph.graph import START, MessagesState, StateGraph
# from langgraph.store.redis import RedisStore
# from langgraph.store.base import BaseStore

# # Set up model
# model = ChatAnthropic(model="claude-3-5-sonnet-20240620")

# # Function that uses store to access and save user memories
# def call_model(state: MessagesState, config: RunnableConfig, *, store: BaseStore):
#     user_id = config["configurable"]["user_id"]
#     namespace = ("memories", user_id)
    
#     # Retrieve relevant memories for this user
#     memories = store.search(namespace, query=str(state["messages"][-1].content))
#     info = "\n".join([d.value["data"] for d in memories])
#     system_msg = f"You are a helpful assistant talking to the user. User info: {info}"
    
#     # Store new memories if the user asks to remember something
#     last_message = state["messages"][-1]
#     if "remember" in last_message.content.lower():
#         memory = "User name is Bob"
#         store.put(namespace, str(uuid.uuid4()), {"data": memory})
    
#     # Generate response
#     response = model.invoke(
#         [{"role": "system", "content": system_msg}] + state["messages"]
#     )
#     return {"messages": response}

# # Build the graph
# builder = StateGraph(MessagesState)
# builder.add_node("call_model", call_model)
# builder.add_edge(START, "call_model")

# # Initialize Redis persistence and store
# REDIS_URI = "redis://localhost:6379"
# with RedisSaver.from_conn_string(REDIS_URI) as checkpointer:
#     checkpointer.setup()
    
#     with RedisStore.from_conn_string(REDIS_URI) as store:
#         store.setup()
        
#         # Compile graph with both checkpointer and store
#         graph = builder.compile(checkpointer=checkpointer, store=store)


import redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
