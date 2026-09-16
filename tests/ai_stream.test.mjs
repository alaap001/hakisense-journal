import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createSSEParser} from '../src/aiStream.mjs';
test('SSE survives single-byte UTF-8 fragments, CRLF, comments and multiline data',()=>{
 const events=[],parser=createSSEParser(e=>events.push(e)),decoder=new TextDecoder();
 const frame=': ping\r\n\r\nid: 12\r\nevent: text\r\ndata: {"delta":"₹ café नमस्ते"}\r\n\r\nevent: snapshot\ndata: {"status":\ndata: "succeeded"}\n\n';
 const bytes=new TextEncoder().encode(frame);
 for(let i=0;i<bytes.length;i++)parser.feed(decoder.decode(bytes.slice(i,i+1),{stream:true}));
 parser.feed(decoder.decode());assert.equal(events.length,2);assert.equal(events[0].data.delta,'₹ café नमस्ते');assert.equal(events[0].id,12);assert.equal(events[1].data.status,'succeeded');
});
