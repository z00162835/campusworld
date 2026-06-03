import { describe, expect, it } from 'vitest'
import { parseStreamEventChunks, parseStreamEventPayload } from '../decisionCenter'

describe('parseStreamEventPayload', () => {
  it('parses delta events', () => {
    const event = parseStreamEventPayload('{"kind":"delta","text":"hi"}')
    expect(event?.kind).toBe('delta')
    expect(event?.text).toBe('hi')
  })

  it('parses tick meta events', () => {
    const event = parseStreamEventPayload('{"kind":"meta","scope":"tick","phase":"start","client_hint":"running"}')
    expect(event?.scope).toBe('tick')
    expect(event?.phase).toBe('start')
  })

  it('parses activity meta events', () => {
    const event = parseStreamEventPayload('{"kind":"meta","scope":"activity","activity":"writing"}')
    expect(event?.scope).toBe('activity')
    expect(event?.activity).toBe('writing')
  })
})

describe('parseStreamEventChunks', () => {
  it('splits SSE frames and keeps remainder', () => {
    const buffer = 'data: {"kind":"delta","text":"a"}\n\ndata: {"kind":"meta","scope":"tick","phase":"do"}\n\ndata: {"kind":"del'
    const { events, remainder } = parseStreamEventChunks(buffer)
    expect(events).toHaveLength(2)
    expect(events[0].text).toBe('a')
    expect(events[1].phase).toBe('do')
    expect(remainder).toContain('del')
  })
})
