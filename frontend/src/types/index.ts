export type Status = 'success' | 'running' | 'failed' | 'idle' | 'warning' | 'pending' | 'disabled'

export interface Agent {
  id: string
  name: string
  description: string
  icon: 'shield' | 'book' | 'flask' | 'workflow'
  model: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  tools: string[]
  knowledgeIds: string[]
  status: 'enabled' | 'disabled'
  lastRunAt: string
  runCount: number
}

export type EmbedModel = 'text-embedding-v3' | 'bge-m3'

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  docCount: number
  chunkCount: number
  embedModel: EmbedModel
  dimension: number
  chunkSize: number
  chunkOverlap: number
  topK: number
  scoreThreshold: number
  hybrid: boolean
  rerank: boolean
  indexStatus: 'ready' | 'indexing' | 'failed'
  updatedAt: string
}

export interface KbDocument {
  id: string
  kbId: string
  name: string
  type: 'md' | 'pdf' | 'docx' | 'xlsx'
  sizeKb: number
  uploadedAt: string
  status: 'ready' | 'processing' | 'failed' | 'cancelled'
  chunkCount: number
  isMock: true
}

export interface Chunk {
  id: string
  docId: string
  docName: string
  section: string
  tokens: number
  position: string
  text: string
  meta: Record<string, string>
}

export interface ChatSource {
  docName: string
  chapter: string
  text: string
  similarity: number
  rerank: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  sources?: ChatSource[]
  refused?: boolean
}

export interface ChatSession {
  id: string
  title: string
  agentId: string
  updatedAt: string
  messages: ChatMessage[]
}

export interface RetrievalHit {
  id: string
  docName: string
  section: string
  text: string
  rawScore: number
  rank: number
  channel: 'bm25' | 'vector' | 'merged'
  rerankRank?: number
  rerankScore?: number
}

export interface WorkflowNode {
  id: string
  type: 'start' | 'llm' | 'retriever' | 'tool' | 'condition' | 'output'
  label: string
  x: number
  y: number
  config: Record<string, string>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
}

export interface Workflow {
  id: string
  name: string
  description: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  status: 'draft' | 'published'
  createdAt: string
  lastRunAt: string | null
}

export interface RunStep {
  nodeId: string
  label: string
  status: Status
  durationMs: number
  input: string
  output: string
  error?: string
}

export interface LogEntry {
  id: string
  taskType: 'chat' | 'retrieval' | 'workflow' | 'evaluation'
  target: string
  startedAt: string
  durationMs: number
  status: 'success' | 'failed' | 'running'
  tokens: number
  steps: RunStep[]
  error?: string
  linkedChunks: string[]
  isMock: true
}

export interface EvalCase {
  id: string
  question: string
  expect: string
  expectDocs: string[]
  tags: string[]
  expectRefuse: boolean
}

export interface EvalTask {
  id: string
  name: string
  target: string
  caseCount: number
  progress: number
  status: 'success' | 'running' | 'failed' | 'pending'
  recall: number | null
  relevance: number | null
  faithfulness: number | null
  failures: { caseId: string; reason: string }[]
  isMock: true
}

export interface AppSettings {
  version: number
  workspaceName: string
  model: { name: string; temperature: number; maxTokens: number; timeoutSec: number }
  embedding: { model: EmbedModel; dimension: number }
  retrieval: { topK: number; scoreThreshold: number; hybrid: boolean; rerank: boolean }
  appearance: { theme: 'light'; density: 'comfortable' | 'compact' }
}
