// Fallback prompts used before any documents have been uploaded.
export const SUGGESTIONS = [
  'What are the main themes across these documents?',
  'What does the uploaded material say about its main topic?',
  'How are the main concepts in these documents related?',
  'Summarize the key findings from the uploaded documents.',
]

const cleanName = (name) => String(name || 'uploaded documents')
  .replace(/\.[^.]+$/, '')
  .replace(/[_-]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()

const unique = (items) => [...new Set(items.filter(Boolean))]

export function getSuggestions(documents = []) {
  const docs = Array.isArray(documents) ? documents.filter(Boolean) : []
  if (!docs.length) return SUGGESTIONS

  const topics = unique(docs.flatMap((document) => Array.isArray(document.topics) ? document.topics : []))
    .map((topic) => typeof topic === 'string' ? topic : topic?.label)
    .filter(Boolean)
  const documentNames = docs.map((document) => cleanName(document.name)).filter(Boolean)
  const primaryTopic = topics[0] || documentNames[0] || 'the uploaded material'
  const secondaryTopic = topics.find((topic) => topic.toLowerCase() !== primaryTopic.toLowerCase())
  const documentLabel = documentNames.length === 1
    ? documentNames[0]
    : `${docs.length} uploaded documents`

  return unique([
    `What are the main themes across ${documentLabel}?`,
    `What do the documents say about ${primaryTopic}?`,
    secondaryTopic
      ? `How are ${primaryTopic} and ${secondaryTopic} related?`
      : `What evidence supports the main points about ${primaryTopic}?`,
    `Summarize the key findings in ${documentLabel}.`,
  ]).slice(0, 4)
}
