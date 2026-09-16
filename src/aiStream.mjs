/** Incremental SSE parser: UTF-8 decoding belongs to the reader; framing survives split chunks. */
export function createSSEParser(onEvent) {
  let buffer = '';
  return {
    feed(text) {
      buffer += text;
      let match;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        let kind = 'message', id, lines = [];
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith(':')) continue;
          const colon = line.indexOf(':');
          const name = colon < 0 ? line : line.slice(0, colon);
          const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (name === 'event') kind = value;
          if (name === 'id') id = Number(value);
          if (name === 'data') lines.push(value);
        }
        if (lines.length) onEvent({kind, id, data: JSON.parse(lines.join('\n'))});
      }
    }
  };
}
