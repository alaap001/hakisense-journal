export function createSSEParser(onEvent:(event:{kind:string;id?:number;data:any})=>void):{feed(text:string):void};
