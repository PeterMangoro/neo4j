function parseSseDataLine(line: string, onDelta: (delta: string) => void): void {
  if (!line.startsWith('data:')) {
    return
  }
  const payload = line.replace(/^data:\s?/, '').trim()
  if (payload === '[DONE]') {
    return
  }
  try {
    const chunk = JSON.parse(payload) as {
      type?: string
      delta?: string
      errorText?: string
    }
    if (chunk.type === 'error' && chunk.errorText) {
      throw new Error(chunk.errorText)
    }
    if (chunk.type === 'text-delta' && typeof chunk.delta === 'string') {
      onDelta(chunk.delta)
    }
  } catch (e) {
    if (e instanceof SyntaxError) {
      return
    }
    throw e
  }
}

/**
 * Consumes the Server-Sent Events body from createUIMessageStreamResponse (AI SDK).
 * Avoids DefaultChatTransport + readUIMessageStream, which can fail silently in the browser
 * when chunk parsing or message-id handling does not match the stream.
 */
export async function consumeDevreotesUiSse(
  body: ReadableStream<Uint8Array>,
  onDelta: (delta: string) => void
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buf += decoder.decode(value, { stream: true })

    let sep: number
    while ((sep = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, sep)
      buf = buf.slice(sep + 2)

      for (const line of block.split('\n')) {
        parseSseDataLine(line, onDelta)
      }
    }
  }

  for (const line of buf.split('\n')) {
    parseSseDataLine(line, onDelta)
  }
}
