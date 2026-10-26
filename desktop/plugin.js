/**
 * Game Shelf — the Hermes Desktop lobby for the Game Shelf plugin.
 *
 * A page (sidebar → Games) with the games on the left, the selected board in the
 * middle, and the lobby chat on the right. Every button and chat line is sent to
 * dashboard/plugin_api.py as a /games line, the same as typing it in the session.
 * The page draws the text board it is given. It does not judge moves or keep a
 * copy of any rules.
 *
 * No side pane on purpose: closing a plugin's only pane disables the plugin.
 * A status-bar button stays so the page is one click away.
 *
 * Plain ESM, loaded uncompiled: jsx() calls only; imports limited to
 * @hermes/plugin-sdk, react, react/jsx-runtime.
 */

import { host, PALETTE_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ROUTE = '/games'
const POLL_MS = 3000

const text = {
  primary: 'var(--ui-text-primary, inherit)',
  secondary: 'var(--ui-text-secondary)',
  tertiary: 'var(--ui-text-tertiary)'
}
const stroke = 'var(--ui-stroke-secondary)'
const accent = 'var(--ui-accent)'

function button(label, onClick, options = {}) {
  return jsx('button', {
    type: 'button',
    onClick,
    disabled: options.disabled,
    title: options.title,
    style: {
      padding: '4px 10px',
      borderRadius: 6,
      border: `1px solid ${stroke}`,
      background: options.primary ? accent : 'transparent',
      color: options.primary ? 'var(--ui-text-on-accent, white)' : text.secondary,
      cursor: options.disabled ? 'default' : 'pointer',
      opacity: options.disabled ? 0.5 : 1,
      fontSize: 12
    },
    children: label
  })
}

function field(value, setValue, placeholder, onEnter) {
  return jsx('input', {
    value,
    placeholder,
    onChange: event => setValue(event.target.value),
    onKeyDown: event => {
      if (event.key === 'Enter' && value.trim()) onEnter()
    },
    style: {
      flex: 1,
      minWidth: 0,
      padding: '4px 8px',
      borderRadius: 6,
      border: `1px solid ${stroke}`,
      background: 'transparent',
      color: 'inherit',
      fontSize: 12
    }
  })
}

function pre(body) {
  return jsx('pre', {
    style: {
      margin: 0,
      padding: 10,
      border: `1px solid ${stroke}`,
      borderRadius: 6,
      fontFamily: 'var(--font-mono, ui-monospace, monospace)',
      fontSize: 12,
      lineHeight: 1.35,
      whiteSpace: 'pre',
      overflow: 'auto'
    },
    children: body
  })
}

function GameShelfPage({ ctx }) {
  const [view, setView] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState('')
  const [boardText, setBoardText] = useState('')
  const [reply, setReply] = useState('')
  const [move, setMove] = useState('')
  const [chat, setChat] = useState('')
  const [name, setName] = useState('')

  const refresh = useCallback(async () => {
    try {
      const next = await ctx.rest('/view')
      setView(next)
      setError('')
      const current = selected || (next.games[0] && next.games[0].id) || ''
      if (current && current !== selected) setSelected(current)
      if (current) {
        const shown = await ctx.rest(`/board?game=${encodeURIComponent(current)}`)
        setBoardText(shown.text || '')
      }
    } catch (failure) {
      setError('The Game Shelf backend is not answering. Add hermes-gameshelf to plugins.enabled in config.yaml and restart Hermes.')
    }
  }, [ctx, selected])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, POLL_MS)
    return () => clearInterval(timer)
  }, [refresh])

  const send = useCallback(
    async line => {
      try {
        const answer = await ctx.rest('/command', { method: 'POST', body: { line } })
        setReply(answer.text || '')
      } catch (failure) {
        setReply('That did not reach the Game Shelf.')
      }
      refresh()
    },
    [ctx, refresh]
  )

  if (error) {
    return jsx('div', { style: { padding: 16, color: text.secondary }, children: error })
  }
  if (!view) {
    return jsx('div', { style: { padding: 16, color: text.tertiary }, children: 'Loading the Game Shelf…' })
  }

  const game = view.games.find(item => item.id === selected) || view.games[0]
  const lobby = view.lobby || { lines: [], looking: [] }

  const left = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', borderRight: `1px solid ${stroke}`, minWidth: 200, overflow: 'auto' },
    children: [
      jsxs('div', {
        style: { padding: '12px 14px', borderBottom: `1px solid ${stroke}` },
        children: [
          jsx('div', { style: { fontWeight: 600 }, children: 'Games' }),
          jsx('div', {
            style: { fontSize: 12, color: text.tertiary },
            children: view.player.named ? `You are ${view.player.name}` : 'Pick a name to chat'
          })
        ]
      }),
      ...view.games.map(item =>
        jsxs(
          'button',
          {
            type: 'button',
            onClick: () => {
              setSelected(item.id)
              setReply('')
            },
            style: {
              textAlign: 'left',
              padding: '10px 14px',
              border: 'none',
              borderLeft: `2px solid ${game && item.id === game.id ? accent : 'transparent'}`,
              background: game && item.id === game.id ? 'var(--ui-fill-tertiary, transparent)' : 'transparent',
              color: 'inherit',
              cursor: 'pointer'
            },
            children: [
              jsx('div', { style: { fontWeight: 600, fontSize: 13 }, children: item.title }),
              jsx('div', {
                style: { fontSize: 11, color: text.tertiary },
                children: item.bots ? 'People or the built-in player' : 'People'
              })
            ]
          },
          item.id
        )
      )
    ]
  })

  const middle = game
    ? jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 10, padding: 14, minWidth: 0, overflow: 'auto' },
        children: [
          jsx('div', { style: { fontWeight: 600, fontSize: 15 }, children: game.title }),
          jsx('div', { style: { fontSize: 12, color: text.secondary }, children: game.summary }),
          jsxs('div', {
            style: { display: 'flex', gap: 6, flexWrap: 'wrap' },
            children: [
              button('New game', () => send(`${game.id} new`), { primary: true }),
              button('Join open seat', () => send(`${game.id} join`)),
              game.bots
                ? button('Play the built-in player', () => send(`allow-ai ${game.id} black=local`), {
                    disabled: !view.allow_ai,
                    title: view.allow_ai ? 'You agree to an AI opponent.' : 'AI seats are off for this profile.'
                  })
                : null,
              button(`Looking for ${game.title}`, () => send(`looking ${game.id}`), { disabled: !view.player.named })
            ]
          }),
          boardText ? pre(boardText) : null,
          jsxs('div', {
            style: { display: 'flex', gap: 6 },
            children: [
              field(move, setMove, 'Your move, as you would type it after "move"', () => {
                send(`${game.id} move ${move.trim()}`)
                setMove('')
              }),
              button('Move', () => {
                send(`${game.id} move ${move.trim()}`)
                setMove('')
              }, { disabled: !move.trim() }),
              button('Resign', () => send(`${game.id} resign`)),
              button('Abandon', () => send(`${game.id} abandon`))
            ]
          }),
          reply ? pre(reply) : null
        ]
      })
    : jsx('div', { style: { padding: 14, color: text.tertiary }, children: 'No games are enabled.' })

  const right = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: 8, padding: 14, borderLeft: `1px solid ${stroke}`, minWidth: 240, overflow: 'auto' },
    children: [
      jsx('div', { style: { fontWeight: 600 }, children: 'Lobby' }),
      view.player.named
        ? null
        : jsxs('div', {
            style: { display: 'flex', gap: 6 },
            children: [
              field(name, setName, 'Your name', () => {
                send(`name ${name.trim()}`)
                setName('')
              }),
              button('Set', () => {
                send(`name ${name.trim()}`)
                setName('')
              }, { disabled: !name.trim() })
            ]
          }),
      jsx('div', {
        style: { fontSize: 12, color: text.secondary },
        children: lobby.looking.length
          ? `Looking: ${lobby.looking.map(item => `${item.name} (${item.game})`).join(', ')}`
          : 'Nobody is looking for a game yet.'
      }),
      jsx('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 4, flex: 1, fontSize: 12 },
        children: lobby.lines.length
          ? lobby.lines.map((item, index) =>
              jsxs(
                'div',
                {
                  children: [
                    jsx('span', { style: { fontWeight: 600 }, children: `${item.name}: ` }),
                    jsx('span', { style: { color: text.secondary }, children: item.text })
                  ]
                },
                index
              )
            )
          : jsx('div', { style: { color: text.tertiary }, children: 'No messages yet.' })
      }),
      jsxs('div', {
        style: { display: 'flex', gap: 6 },
        children: [
          field(chat, setChat, view.player.named ? 'Say something' : 'Set a name first', () => {
            send(`chat say ${chat.trim()}`)
            setChat('')
          }),
          button('Send', () => {
            send(`chat say ${chat.trim()}`)
            setChat('')
          }, { disabled: !chat.trim() || !view.player.named })
        ]
      })
    ]
  })

  return jsx('div', {
    style: { display: 'grid', gridTemplateColumns: 'minmax(200px, 240px) 1fr minmax(240px, 300px)', height: '100%', minHeight: 0 },
    children: [left, middle, right]
  })
}

export default {
  id: 'hermes-gameshelf',
  name: 'Game Shelf',
  register(ctx) {
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: ROUTE },
        render: () => jsx(GameShelfPage, { ctx })
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: ROUTE, label: 'Games', codicon: 'game' }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'hermes-gameshelf.open',
          label: 'Open Game Shelf',
          keywords: ['games', 'shelf', 'lobby', 'chess', 'checkers'],
          run: () => host.navigate(ROUTE)
        }
      },
      {
        id: 'status',
        area: STATUSBAR_AREAS.right,
        order: 140,
        render: () =>
          jsx('button', {
            type: 'button',
            title: 'Open the Game Shelf',
            onClick: () => host.navigate(ROUTE),
            style: {
              padding: '0 6px',
              border: 'none',
              background: 'transparent',
              color: text.tertiary,
              fontSize: 11,
              cursor: 'pointer'
            },
            children: 'Games'
          })
      }
    ])
  }
}
