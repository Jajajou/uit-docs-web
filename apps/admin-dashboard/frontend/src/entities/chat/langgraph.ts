import { Client } from "@langchain/langgraph-sdk";

// Use the current origin as the API URL, we'll proxy /api/student to the backend
const API_URL = typeof window !== "undefined" ? `${window.location.origin}/api/student` : "http://localhost:8001/api/student";

export const langgraphClient = new Client({
  apiUrl: API_URL,
});
