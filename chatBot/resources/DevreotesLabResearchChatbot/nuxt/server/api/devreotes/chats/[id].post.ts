import { createUIMessageStream, createUIMessageStreamResponse } from 'ai'
import { db, schema } from 'hub:db'
import { and, eq } from 'drizzle-orm'
import { randomUUID } from 'node:crypto'
import { spawn } from 'node:child_process'
import readline from 'node:readline'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { z } from 'zod'
import {
  applyDevreotesNdjsonLine,
  consumeDevreotesNdjsonStream,
  type DevreotesFinishBox
} from '../../../utils/devreotesNdjson'
import { buildDevreotesTrace } from '../../../types/devreotes-trace'

export default defineEventHandler(async (event) => {
  const session = await getUserSession(event)
  const { id } = await getValidatedRouterParams(event, z.object({
    id: z.string()
  }).parse)

  const { message, skipUserInsert } = await readValidatedBody(event, z.object({
    message: z.string().min(1),
    skipUserInsert: z.boolean().optional()
  }).parse)

  const chat = await db.query.chats.findFirst({
    where: () => and(
      eq(schema.chats.id, id as string),
      eq(schema.chats.userId, session.user?.id || session.id)
    )
  })
  if (!chat) {
    throw createError({ statusCode: 404, statusMessage: 'Chat not found' })
  }

  if (!skipUserInsert) {
    await db.insert(schema.messages).values({
      chatId: id as string,
      role: 'user',
      parts: [{ type: 'text', text: message }]
    })
  }

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      const textId = randomUUID()

      const nuxtRoot = process.cwd()
      const devreotesRoot = process.env.DEVREOTES_ROOT || resolve(nuxtRoot, '..')
      const scriptPath = resolve(nuxtRoot, 'server/python/devreotes_bridge.py')
      const venvPython = resolve(devreotesRoot, '.venv/bin/python')
      const pythonBin
        = process.env.DEVREOTES_PYTHON
          || (existsSync(venvPython) ? venvPython : 'python3')

      writer.write({ type: 'text-start', id: textId })

      const finishBox: DevreotesFinishBox = {
        result: null
      }

      const apiBase = process.env.DEVREOTES_API_URL?.trim()
      if (apiBase) {
        const secret = process.env.DEVREOTES_API_SECRET?.trim()
        const headers: Record<string, string> = {
          'Content-Type': 'application/json'
        }
        if (secret) {
          headers['X-Devreotes-Key'] = secret
        }
        const url = `${apiBase.replace(/\/$/, '')}/chat/stream`
        const res = await fetch(url, {
          method: 'POST',
          headers,
          body: JSON.stringify({ message })
        })
        if (!res.ok) {
          const errText = await res.text().catch(() => '')
          console.error('[devreotes] HTTP API error', {
            url,
            status: res.status,
            body: errText?.slice(0, 500)
          })
          throw new Error(errText || `Devreotes API HTTP ${res.status}`)
        }
        if (!res.body) {
          throw new Error('Empty response body from Devreotes API')
        }
        await consumeDevreotesNdjsonStream(res.body, writer, textId, finishBox)
      } else {
        let stderr = ''
        const proc = spawn(pythonBin, [scriptPath], {
          cwd: devreotesRoot,
          env: {
            ...process.env,
            DEVREOTES_ROOT: devreotesRoot,
            DEVREOTES_STREAM: '1',
            PYTHONUNBUFFERED: '1',
            CUDA_VISIBLE_DEVICES: process.env.CUDA_VISIBLE_DEVICES ?? ''
          }
        })

        proc.stderr?.on('data', (chunk: Buffer) => {
          stderr += chunk.toString()
        })

        await new Promise<void>((resolvePromise, rejectPromise) => {
          const rl = readline.createInterface({ input: proc.stdout, crlfDelay: Infinity })

          rl.on('line', (line) => {
            const trimmed = line.trim()
            applyDevreotesNdjsonLine(trimmed, writer, textId, finishBox)
          })

          proc.on('error', rejectPromise)
          proc.on('close', (code) => {
            rl.close()
            if (code !== 0) {
              const detail = finishBox.bridgeError || stderr || '(no message)'
              console.error('[devreotes] Python bridge failed', {
                code,
                pythonBin,
                scriptPath,
                devreotesRoot,
                stderr: stderr || '(empty)',
                stdoutError: finishBox.bridgeError ?? '(none parsed)'
              })
              rejectPromise(
                new Error(
                  finishBox.bridgeError
                    || stderr
                    || `Bridge exited with code ${code}`
                )
              )
            } else {
              resolvePromise()
            }
          })

          proc.stdin.write(message)
          proc.stdin.end()
        })
      }

      writer.write({ type: 'text-end', id: textId })
      writer.write({ type: 'finish' })

      const finishResult = finishBox.result
      if (!finishResult) {
        throw createError({ statusCode: 500, statusMessage: 'No finish payload from Devreotes backend' })
      }
      if (finishResult.error) {
        throw createError({ statusCode: 500, statusMessage: String(finishResult.error) })
      }

      const answer = (finishResult.answer || '').trim() || 'No response produced by backend.'
      const traceBackend = apiBase ? 'http' : 'bridge'
      await db.insert(schema.messages).values({
        chatId: id as string,
        role: 'assistant',
        parts: [{ type: 'text', text: answer }],
        devreotesTrace: buildDevreotesTrace(finishResult, traceBackend)
      })

      if (!chat.title) {
        await db.update(schema.chats)
          .set({ title: message.slice(0, 30) })
          .where(eq(schema.chats.id, id as string))
      }
    }
  })

  return createUIMessageStreamResponse({ stream })
})
