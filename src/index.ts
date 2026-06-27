interface Fetcher {
  fetch(request: Request): Promise<Response>;
}

export interface Env {
  OPENAI_API_KEY: string;
  ASSETS: Fetcher;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith('/api/ai/')) {
      const upstreamPath = url.pathname.replace('/api/ai', '');
      const upstreamApiUrl = `https://api.openai.com${upstreamPath}${url.search}`;

      // Forward original headers, then inject auth
      const forwardedHeaders = new Headers(request.headers);
      forwardedHeaders.set('authorization', `Bearer ${env.OPENAI_API_KEY}`);
      // Remove host header so it doesn't conflict with the upstream host
      forwardedHeaders.delete('host');
      forwardedHeaders.delete('origin');
      forwardedHeaders.delete('referer');

      const upstreamRequest = new Request(upstreamApiUrl, {
        method: request.method,
        headers: forwardedHeaders,
        body: request.body,
      });

      const response = await fetch(upstreamRequest);

      // Filter hop-by-hop headers that shouldn't be forwarded
      const responseHeaders = new Headers(response.headers);
      responseHeaders.delete('content-encoding');
      responseHeaders.delete('transfer-encoding');
      responseHeaders.set('access-control-allow-origin', '*');

      return new Response(response.body, {
        status: response.status,
        headers: responseHeaders,
      });
    }

    // SPA fallback: serve index.html for all non-asset routes
    const assetResponse = await env.ASSETS.fetch(request);
    if (assetResponse.status === 404) {
      return env.ASSETS.fetch(new Request(new URL('/', request.url).toString(), request));
    }
    return assetResponse;
  },
};
