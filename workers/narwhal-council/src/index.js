var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// NARWHAL COUNCIL RELAY - FULLY CORRECTED VERSION
// All IPs updated to 192.168.1.219
// All camera refs updated to 48MP Arducam
// Patent claims updated to 117

var CONFIG = {
  SERVICES: {},
  SERVER_INFO: {
    name: "narwhal-council",
    version: "1.1.0",
    protocolVersion: "2024-11-05"
  },
  TOOLS: [
    {
      name: "report_scanner_status",
      description: "Scanner reports its status TO the relay (called by DANIELSON/ZULTAN)",
      inputSchema: {
        type: "object",
        properties: {
          scanner_id: { type: "string", description: "Scanner identifier (DANIELSON, ZULTAN)" },
          status: { type: "string", enum: ["online", "scanning", "idle", "error", "offline"] },
          data: { type: "object", description: "Optional status data (scan count, queue, etc.)" }
        },
        required: ["scanner_id", "status"]
      }
    },
    {
      name: "get_scanner_status",
      description: "Get last known status from DANIELSON/ZULTAN",
      inputSchema: {
        type: "object",
        properties: {
          scanner_id: { type: "string", description: "Specific scanner ID, or omit for all" }
        }
      }
    },
    {
      name: "relay_message",
      description: "Send a message to another Narwhal Council agent",
      inputSchema: {
        type: "object",
        properties: {
          from: { type: "string", enum: ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"], description: "Your agent name (sender)" },
          to: { type: "string", enum: ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"], description: "Target agent" },
          message: { type: "string", description: "Message content" },
          priority: { type: "string", enum: ["low", "normal", "high", "urgent"], default: "normal" }
        },
        required: ["from", "to", "message"]
      }
    },
    {
      name: "get_messages",
      description: "Get messages from your inbox (messages sent to you)",
      inputSchema: {
        type: "object",
        properties: {
          agent: { type: "string", enum: ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"], description: "Your agent name to retrieve messages for" },
          mark_read: { type: "boolean", description: "Mark messages as read after retrieval", default: false }
        },
        required: ["agent"]
      }
    },
    {
      name: "get_agent_outbox",
      description: "Get all messages SENT BY a specific agent (what did that agent say?)",
      inputSchema: {
        type: "object",
        properties: {
          agent: { type: "string", enum: ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"], description: "Agent whose sent messages to retrieve" },
          limit: { type: "integer", description: "Max messages to return", default: 20 }
        },
        required: ["agent"]
      }
    },
    {
      name: "get_knowledge",
      description: "Retrieve information from the shared NEXUS knowledge base (investor docs, business data, file locations, etc.)",
      inputSchema: {
        type: "object",
        properties: {
          key: { type: "string", description: "Knowledge key (e.g., 'investor_docs', 'business_metrics', 'file_locations')" },
          category: { type: "string", description: "Optional category filter" }
        },
        required: ["key"]
      }
    },
    {
      name: "set_knowledge",
      description: "Store information in the shared NEXUS knowledge base (Klaus/Mendel use for updating shared data)",
      inputSchema: {
        type: "object",
        properties: {
          key: { type: "string", description: "Knowledge key" },
          value: { type: "object", description: "Data to store (any JSON object)" },
          category: { type: "string", description: "Optional category for organization" },
          description: { type: "string", description: "Human-readable description of this knowledge" }
        },
        required: ["key", "value"]
      }
    },
    {
      name: "search_knowledge",
      description: "Search the NEXUS knowledge base for keys matching a query",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search term" },
          category: { type: "string", description: "Optional category filter" }
        },
        required: ["query"]
      }
    },
    {
      name: "get_patent_claims",
      description: "Retrieve patent claim information (117 claims)",
      inputSchema: {
        type: "object",
        properties: {
          claim_number: { type: "integer", description: "Specific claim number (1-117), or omit for summary" },
          category: { type: "string", enum: ["system", "method", "apparatus", "ai", "network", "all"], default: "all" }
        }
      }
    },
    {
      name: "get_council_status",
      description: "Get status of all Narwhal Council agents and services",
      inputSchema: {
        type: "object",
        properties: {}
      }
    },
    {
      name: "check_email",
      description: "Check the NEXUS email inbox for new messages",
      inputSchema: {
        type: "object",
        properties: {
          mark_read: { type: "boolean", description: "Mark emails as read after retrieval", default: false },
          limit: { type: "integer", description: "Max emails to return", default: 10 }
        }
      }
    },
    {
      name: "send_email_notification",
      description: "Queue an email notification to be sent (internal use)",
      inputSchema: {
        type: "object",
        properties: {
          to: { type: "string", description: "Recipient email" },
          subject: { type: "string", description: "Email subject" },
          body: { type: "string", description: "Email body" }
        },
        required: ["to", "subject", "body"]
      }
    },
    {
      name: "post_tweet",
      description: "Post a tweet to the NEXUS X/Twitter account (Jaques use)",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string", description: "Tweet content (max 280 chars)", maxLength: 280 },
          reply_to: { type: "string", description: "Tweet ID to reply to (optional)" }
        },
        required: ["text"]
      }
    },
    {
      name: "read_mentions",
      description: "Read recent mentions/replies to the NEXUS X account",
      inputSchema: {
        type: "object",
        properties: {
          limit: { type: "integer", description: "Max mentions to return", default: 10 },
          since_id: { type: "string", description: "Only get mentions after this tweet ID" }
        }
      }
    },
    {
      name: "search_tweets",
      description: "Search X for tweets about MTG, collectibles, or NEXUS",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: 'Search query (e.g., "#MTG", "card grading")' },
          limit: { type: "integer", description: "Max results", default: 20 }
        },
        required: ["query"]
      }
    },
    {
      name: "get_twitter_timeline",
      description: "Get recent tweets from NEXUS timeline or home feed",
      inputSchema: {
        type: "object",
        properties: {
          timeline_type: { type: "string", enum: ["own", "home"], default: "own" },
          limit: { type: "integer", default: 10 }
        }
      }
    },
    {
      name: "post_linkedin",
      description: "Post an update to the NEXUS LinkedIn company page",
      inputSchema: {
        type: "object",
        properties: {
          text: { type: "string", description: "Post content (max 3000 chars)" },
          article_url: { type: "string", description: "Optional URL to share" },
          article_title: { type: "string", description: "Title for shared article" }
        },
        required: ["text"]
      }
    },
    {
      name: "get_linkedin_analytics",
      description: "Get engagement analytics for NEXUS LinkedIn page",
      inputSchema: {
        type: "object",
        properties: {
          time_range: { type: "string", enum: ["day", "week", "month"], default: "week" }
        }
      }
    },
    {
      name: "search_linkedin",
      description: "Search LinkedIn for collectibles industry content and connections",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query" },
          content_type: { type: "string", enum: ["posts", "people", "companies"], default: "posts" }
        },
        required: ["query"]
      }
    },
    {
      name: "post_reddit",
      description: "Post to a subreddit (r/mtg, r/mtgfinance, r/Pokemon, etc.)",
      inputSchema: {
        type: "object",
        properties: {
          subreddit: { type: "string", description: 'Subreddit name without r/ (e.g., "mtgfinance")' },
          title: { type: "string", description: "Post title" },
          text: { type: "string", description: "Post body text (for text posts)" },
          url: { type: "string", description: "URL to share (for link posts)" },
          flair: { type: "string", description: "Post flair if required by subreddit" }
        },
        required: ["subreddit", "title"]
      }
    },
    {
      name: "read_reddit_posts",
      description: "Read posts from a subreddit",
      inputSchema: {
        type: "object",
        properties: {
          subreddit: { type: "string", description: "Subreddit name without r/" },
          sort: { type: "string", enum: ["hot", "new", "top", "rising"], default: "hot" },
          limit: { type: "integer", description: "Number of posts to fetch", default: 10 }
        },
        required: ["subreddit"]
      }
    },
    {
      name: "comment_reddit",
      description: "Comment on a Reddit post",
      inputSchema: {
        type: "object",
        properties: {
          post_id: { type: "string", description: "Reddit post ID (t3_xxxxx)" },
          text: { type: "string", description: "Comment text" }
        },
        required: ["post_id", "text"]
      }
    },
    {
      name: "search_reddit",
      description: "Search Reddit for NEXUS mentions or collectibles topics",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query" },
          subreddit: { type: "string", description: "Limit to specific subreddit (optional)" },
          sort: { type: "string", enum: ["relevance", "hot", "top", "new", "comments"], default: "relevance" },
          limit: { type: "integer", default: 25 }
        },
        required: ["query"]
      }
    },
    {
      name: "capture_camera",
      description: "Capture a snapshot from DANIELSON scanner camera (Arducam 48MP, webcam)",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson"], default: "danielson", description: "Scanner to capture from" },
          camera: { type: "string", enum: ["arducam", "webcam"], default: "arducam", description: "Camera to use" },
          analyze: { type: "boolean", default: true, description: "Run card detection on captured image" }
        }
      }
    },
    {
      name: "get_camera_status",
      description: "Check status of all cameras on the scanner network",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson", "all"], default: "all" }
        }
      }
    },
    {
      name: "view_scan_area",
      description: "Get current view of the scan area with card detection results",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson"], default: "danielson" },
          include_ocr: { type: "boolean", default: false, description: "Include OCR text extraction" }
        }
      }
    },
    {
      name: "get_last_scan",
      description: "Get the most recent scan result from a scanner",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson"], default: "danielson" }
        }
      }
    },
    {
      name: "list_scan_files",
      description: "List recent scan files on a scanner (images, OCR results)",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson"], default: "danielson" },
          limit: { type: "integer", default: 20, description: "Max files to return" },
          filter: { type: "string", enum: ["all", "images", "today"], default: "all" }
        }
      }
    },
    {
      name: "get_scan_file",
      description: "Get details and content of a specific scan file (includes base64 thumbnail)",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson"], default: "danielson" },
          filename: { type: "string", description: "Filename to retrieve" },
          include_thumbnail: { type: "boolean", default: true, description: "Include base64 thumbnail" }
        },
        required: ["filename"]
      }
    },
    {
      name: "search_scan_files",
      description: "Search scan files by card name, date, or camera",
      inputSchema: {
        type: "object",
        properties: {
          scanner: { type: "string", enum: ["danielson"], default: "danielson" },
          query: { type: "string", description: "Search term (card name, date, camera type)" },
          limit: { type: "integer", default: 10 }
        },
        required: ["query"]
      }
    }
  ]
};

var CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
  "Access-Control-Max-Age": "86400"
};

function generateToken(clientId, env) {
  const timestamp = Date.now();
  const data = `${clientId}:${timestamp}:narwhal`;
  return btoa(data);
}
__name(generateToken, "generateToken");

async function handleOAuthToken(request, env) {
  try {
    const contentType = request.headers.get("Content-Type") || "";
    let clientId, clientSecret, grantType, code, codeVerifier, redirectUri;
    if (contentType.includes("application/x-www-form-urlencoded")) {
      const formData = await request.formData();
      clientId = formData.get("client_id");
      clientSecret = formData.get("client_secret");
      grantType = formData.get("grant_type");
      code = formData.get("code");
      codeVerifier = formData.get("code_verifier");
      redirectUri = formData.get("redirect_uri");
    } else {
      const body = await request.json();
      clientId = body.client_id;
      clientSecret = body.client_secret;
      grantType = body.grant_type;
      code = body.code;
      codeVerifier = body.code_verifier;
      redirectUri = body.redirect_uri;
    }
    if (grantType !== "client_credentials" && grantType !== "authorization_code") {
      return new Response(JSON.stringify({
        error: "unsupported_grant_type",
        error_description: "Supported grant types: client_credentials, authorization_code"
      }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
      });
    }
    if (grantType === "authorization_code") {
      if (!code) {
        return new Response(JSON.stringify({
          error: "invalid_request",
          error_description: "Missing authorization code"
        }), {
          status: 400,
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
        });
      }
      console.log("Authorization code flow - code received, generating token");
    }
    const validClientId = env.OAUTH_CLIENT_ID;
    const validClientSecret = env.OAUTH_CLIENT_SECRET;
    if (!validClientId || !validClientSecret) {
      console.warn("OAuth credentials not configured - running in dev mode");
    } else if (grantType === "client_credentials" && (clientId !== validClientId || clientSecret !== validClientSecret)) {
      return new Response(JSON.stringify({
        error: "invalid_client",
        error_description: "Invalid client credentials"
      }), {
        status: 401,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
      });
    }
    const accessToken = generateToken(clientId || "claude-ai", env);
    return new Response(JSON.stringify({
      access_token: accessToken,
      token_type: "Bearer",
      expires_in: 86400,
      scope: "mcp:tools"
    }), {
      status: 200,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      error: "server_error",
      error_description: error.message
    }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
    });
  }
}
__name(handleOAuthToken, "handleOAuthToken");

async function handleOAuthAuthorize(request, env) {
  const url = new URL(request.url);
  const redirectUri = url.searchParams.get("redirect_uri");
  const state = url.searchParams.get("state");
  const clientId = url.searchParams.get("client_id");
  const code = btoa(`${clientId}:${Date.now()}:auth`);
  if (redirectUri) {
    const redirectUrl = new URL(redirectUri);
    redirectUrl.searchParams.set("code", code);
    if (state) redirectUrl.searchParams.set("state", state);
    return Response.redirect(redirectUrl.toString(), 302);
  }
  return new Response(JSON.stringify({ code, state }), {
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
  });
}
__name(handleOAuthAuthorize, "handleOAuthAuthorize");

function createMCPResponse(id, result) {
  return {
    jsonrpc: "2.0",
    id,
    result
  };
}
__name(createMCPResponse, "createMCPResponse");

function createMCPError(id, code, message) {
  return {
    jsonrpc: "2.0",
    id,
    error: { code, message }
  };
}
__name(createMCPError, "createMCPError");

async function handleInitialize(id) {
  return createMCPResponse(id, {
    protocolVersion: CONFIG.SERVER_INFO.protocolVersion,
    capabilities: {
      tools: {}
    },
    serverInfo: {
      name: CONFIG.SERVER_INFO.name,
      version: CONFIG.SERVER_INFO.version
    }
  });
}
__name(handleInitialize, "handleInitialize");

async function handleListTools(id) {
  return createMCPResponse(id, {
    tools: CONFIG.TOOLS
  });
}
__name(handleListTools, "handleListTools");

async function handleCallTool(id, params, env) {
  const { name, arguments: args } = params;
  try {
    let result;
    switch (name) {
      case "report_scanner_status":
        result = await reportScannerStatus(args, env);
        break;
      case "get_scanner_status":
        result = await getScannerStatus(args, env);
        break;
      case "relay_message":
        result = await relayMessage(args, env);
        break;
      case "get_patent_claims":
        result = await getPatentClaims(args);
        break;
      case "get_council_status":
        result = await getCouncilStatus(env);
        break;
      case "get_messages":
        result = await getMessages(args, env);
        break;
      case "check_email":
        result = await checkEmail(args, env);
        break;
      case "get_agent_outbox":
        result = await getAgentOutbox(args, env);
        break;
      case "get_knowledge":
        result = await getKnowledge(args, env);
        break;
      case "set_knowledge":
        result = await setKnowledge(args, env);
        break;
      case "search_knowledge":
        result = await searchKnowledge(args, env);
        break;
      case "send_email_notification":
        result = await sendEmailNotification(args, env);
        break;
      case "post_tweet":
        result = await postTweet(args, env);
        break;
      case "read_mentions":
        result = await readMentions(args, env);
        break;
      case "search_tweets":
        result = await searchTweets(args, env);
        break;
      case "get_twitter_timeline":
        result = await getTwitterTimeline(args, env);
        break;
      case "post_linkedin":
        result = await postLinkedIn(args, env);
        break;
      case "get_linkedin_analytics":
        result = await getLinkedInAnalytics(args, env);
        break;
      case "search_linkedin":
        result = await searchLinkedIn(args, env);
        break;
      case "post_reddit":
        result = await postReddit(args, env);
        break;
      case "read_reddit_posts":
        result = await readRedditPosts(args, env);
        break;
      case "comment_reddit":
        result = await commentReddit(args, env);
        break;
      case "search_reddit":
        result = await searchReddit(args, env);
        break;
      case "capture_camera":
        result = await captureCamera(args, env);
        break;
      case "get_camera_status":
        result = await getCameraStatus(args, env);
        break;
      case "view_scan_area":
        result = await viewScanArea(args, env);
        break;
      case "get_last_scan":
        result = await getLastScan(args, env);
        break;
      case "list_scan_files":
        result = await listScanFiles(args, env);
        break;
      case "get_scan_file":
        result = await getScanFile(args, env);
        break;
      case "search_scan_files":
        result = await searchScanFiles(args, env);
        break;
      default:
        return createMCPError(id, -32601, `Unknown tool: ${name}`);
    }
    return createMCPResponse(id, {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }]
    });
  } catch (error) {
    return createMCPError(id, -32e3, error.message);
  }
}
__name(handleCallTool, "handleCallTool");

var scannerStatus = {};

async function getMessagesFromKV(agent, env) {
  if (!env.MESSAGES) {
    console.warn("KV not configured - using empty array");
    return [];
  }
  try {
    const data = await env.MESSAGES.get(`messages:${agent}`, { type: "json" });
    return data || [];
  } catch (error) {
    console.error("KV read error:", error);
    return [];
  }
}
__name(getMessagesFromKV, "getMessagesFromKV");

async function saveMessagesToKV(agent, messages, env) {
  if (!env.MESSAGES) {
    console.warn("KV not configured - messages will not persist");
    return { success: false, error: "KV_NOT_CONFIGURED" };
  }
  try {
    const trimmed = messages.slice(-100);
    await env.MESSAGES.put(`messages:${agent}`, JSON.stringify(trimmed));
    const senders = {};
    for (const msg of trimmed) {
      if (msg.from && msg.from !== agent) {
        if (!senders[msg.from]) senders[msg.from] = [];
        senders[msg.from].push(msg);
      }
    }
    for (const sender of Object.keys(senders)) {
      const existing = await env.MESSAGES.get(`sent_messages:${sender}`, { type: "json" }) || [];
      const combined = [...existing, ...senders[sender]].slice(-100);
      await env.MESSAGES.put(`sent_messages:${sender}`, JSON.stringify(combined));
    }
    return { success: true };
  } catch (error) {
    console.error("KV write error:", error);
    return { success: false, error: error.message || "KV_WRITE_FAILED" };
  }
}
__name(saveMessagesToKV, "saveMessagesToKV");

async function reportScannerStatus(args, env) {
  const { scanner_id, status, data } = args;
  scannerStatus[scanner_id] = {
    status,
    data: data || {},
    last_seen: (new Date()).toISOString()
  };
  return {
    success: true,
    scanner_id,
    acknowledged: true,
    timestamp: (new Date()).toISOString()
  };
}
__name(reportScannerStatus, "reportScannerStatus");

async function getScannerStatus(args, env) {
  const { scanner_id } = args;
  if (scanner_id && scannerStatus[scanner_id]) {
    return scannerStatus[scanner_id];
  }
  return {
    scanners: scannerStatus,
    timestamp: (new Date()).toISOString()
  };
}
__name(getScannerStatus, "getScannerStatus");

async function relayMessage(args, env) {
  const validAgents = ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"];
  if (!validAgents.includes(args.to)) {
    return {
      success: false,
      error: "Invalid recipient agent",
      valid_agents: validAgents
    };
  }
  const messageId = crypto.randomUUID();
  const timestamp = (new Date()).toISOString();
  const message = {
    messageId,
    from: args.from || "UNKNOWN",
    to: args.to,
    message: args.message,
    priority: args.priority || "normal",
    status: "unread",
    timestamp
  };
  const messages = await getMessagesFromKV(args.to, env);
  messages.push(message);
  const saveResult = await saveMessagesToKV(args.to, messages, env);
  return {
    success: true,
    messageId,
    from: args.from,
    to: args.to,
    priority: args.priority || "normal",
    status: saveResult.success ? "delivered_persistent" : "delivered_ephemeral",
    timestamp,
    note: saveResult.success ? "Message stored in KV (persistent)" : `KV error: ${saveResult.error}`,
    kv_debug: { env_has_messages: !!env.MESSAGES, save_result: saveResult }
  };
}
__name(relayMessage, "relayMessage");

async function getMessages(args, env) {
  const { agent, mark_read } = args;
  const validAgents = ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"];
  if (!validAgents.includes(agent)) {
    return {
      error: "Unknown agent",
      valid_agents: validAgents
    };
  }
  const messages = await getMessagesFromKV(agent, env);
  const unreadCount = messages.filter((m) => m.status === "unread").length;
  if (mark_read && messages.length > 0) {
    messages.forEach((m) => m.status = "read");
    await saveMessagesToKV(agent, messages, env);
  }
  return {
    agent,
    total_messages: messages.length,
    unread_count: unreadCount,
    messages: messages.slice(-20),
    storage: env.MESSAGES ? "kv_persistent" : "none",
    timestamp: (new Date()).toISOString()
  };
}
__name(getMessages, "getMessages");

async function getAgentOutbox(args, env) {
  const { agent, limit = 20 } = args;
  const validAgents = ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"];
  if (!validAgents.includes(agent)) {
    return { error: "Unknown agent", valid_agents: validAgents };
  }
  const outbox = await env.MESSAGES.get(`sent_messages:${agent}`, { type: "json" }) || [];
  return {
    agent,
    total_sent: outbox.length,
    messages: outbox.slice(-limit),
    storage: "kv_persistent",
    timestamp: (new Date()).toISOString()
  };
}
__name(getAgentOutbox, "getAgentOutbox");

async function getKnowledge(args, env) {
  const { key, category } = args;
  const knowledge = await env.MESSAGES.get(`knowledge:${key}`, { type: "json" });
  if (!knowledge) {
    return {
      found: false,
      key,
      message: `No knowledge found for key '${key}'. Use set_knowledge to add it.`
    };
  }
  return {
    found: true,
    key,
    value: knowledge.value,
    category: knowledge.category,
    description: knowledge.description,
    last_updated: knowledge.timestamp,
    updated_by: knowledge.agent
  };
}
__name(getKnowledge, "getKnowledge");

async function setKnowledge(args, env) {
  const { key, value, category, description } = args;
  const knowledge = {
    value,
    category: category || "general",
    description: description || "",
    timestamp: (new Date()).toISOString(),
    agent: "MENDEL"
  };
  await env.MESSAGES.put(`knowledge:${key}`, JSON.stringify(knowledge));
  return {
    success: true,
    key,
    message: `Knowledge stored for key '${key}'`
  };
}
__name(setKnowledge, "setKnowledge");

async function searchKnowledge(args, env) {
  const { query, category } = args;
  const results = [];
  const commonKeys = [
    "investor_docs",
    "business_metrics",
    "file_locations",
    "revenue_projections",
    "shop_count",
    "patent_summary",
    "deployment_status",
    "api_endpoints",
    "server_ips",
    "database_locations",
    "contract_templates"
  ];
  for (const key of commonKeys) {
    const knowledge = await env.MESSAGES.get(`knowledge:${key}`, { type: "json" });
    if (knowledge && (key.toLowerCase().includes(query.toLowerCase()) || knowledge.description && knowledge.description.toLowerCase().includes(query.toLowerCase()) || knowledge.category && knowledge.category === category)) {
      results.push({
        key,
        category: knowledge.category,
        description: knowledge.description,
        last_updated: knowledge.timestamp
      });
    }
  }
  return {
    query,
    results_count: results.length,
    results
  };
}
__name(searchKnowledge, "searchKnowledge");

async function getPatentClaims(args) {
  const claims = {
    total: 117,
    independent: 52,
    dependent: 65,
    categories: {
      system: { range: "1-35", count: 35 },
      method: { range: "36-58", count: 23 },
      apparatus: { range: "59-75", count: 17 },
      ai_ml: { range: "76-85", count: 10 },
      marketplace: { range: "86-95", count: 10 },
      network: { range: "96-115", count: 20 },
      master: { range: "116-117", count: 2 }
    },
    nuclearClaims: [99, 115, 116, 117],
    filingDate: "2025-11-27",
    conversionDeadline: "2026-11-27",
    usptoFee: 3830
  };
  if (args && args.claim_number) {
    return {
      claim: args.claim_number,
      note: "Full claim text available in patent_extracted.txt",
      category: getClaimCategory(args.claim_number)
    };
  }
  return claims;
}
__name(getPatentClaims, "getPatentClaims");

function getClaimCategory(num) {
  if (num <= 35) return "system";
  if (num <= 58) return "method";
  if (num <= 75) return "apparatus";
  if (num <= 85) return "ai_ml";
  if (num <= 95) return "marketplace";
  if (num <= 115) return "network";
  return "master";
}
__name(getClaimCategory, "getClaimCategory");

async function getEmailsFromKV(env) {
  if (!env.MESSAGES) return [];
  try {
    const data = await env.MESSAGES.get("emails:inbox", { type: "json" });
    return data || [];
  } catch (error) {
    console.error("KV email read error:", error);
    return [];
  }
}
__name(getEmailsFromKV, "getEmailsFromKV");

async function saveEmailsToKV(emails, env) {
  if (!env.MESSAGES) return false;
  try {
    const trimmed = emails.slice(-100);
    await env.MESSAGES.put("emails:inbox", JSON.stringify(trimmed));
    return true;
  } catch (error) {
    console.error("KV email write error:", error);
    return false;
  }
}
__name(saveEmailsToKV, "saveEmailsToKV");

async function checkEmail(args, env) {
  const { mark_read, limit } = args;
  const maxLimit = limit || 10;
  const emails = await getEmailsFromKV(env);
  const unreadCount = emails.filter((e) => e.status === "unread").length;
  if (mark_read && emails.length > 0) {
    emails.forEach((e) => e.status = "read");
    await saveEmailsToKV(emails, env);
  }
  return {
    total_emails: emails.length,
    unread_count: unreadCount,
    emails: emails.slice(-maxLimit).reverse(),
    storage: env.MESSAGES ? "kv_persistent" : "none",
    note: "Emails forwarded from nexus-cards.com via Cloudflare Email Routing",
    timestamp: (new Date()).toISOString()
  };
}
__name(checkEmail, "checkEmail");

async function sendEmailNotification(args, env) {
  const { to, subject, body } = args;
  return {
    success: true,
    note: "Email queued (outbound email requires SendGrid/Mailgun integration)",
    to,
    subject,
    timestamp: (new Date()).toISOString()
  };
}
__name(sendEmailNotification, "sendEmailNotification");

async function handleIncomingEmail(request, env) {
  try {
    const body = await request.json();
    const email = {
      id: crypto.randomUUID(),
      from: body.from || body.sender || "unknown",
      to: body.to || body.recipient || "team@nexus-cards.com",
      subject: body.subject || "(no subject)",
      body: body.body || body.text || body.html || "",
      status: "unread",
      received_at: (new Date()).toISOString()
    };
    const emails = await getEmailsFromKV(env);
    emails.push(email);
    await saveEmailsToKV(emails, env);
    const notification = {
      messageId: crypto.randomUUID(),
      from: "EMAIL_SYSTEM",
      to: "CLOUSE",
      message: `New email from ${email.from}: "${email.subject}"`,
      priority: "high",
      status: "unread",
      timestamp: (new Date()).toISOString()
    };
    const clouseMessages = await getMessagesFromKV("CLOUSE", env);
    clouseMessages.push(notification);
    await saveMessagesToKV("CLOUSE", clouseMessages, env);
    return new Response(JSON.stringify({
      success: true,
      email_id: email.id,
      message: "Email received and stored"
    }), {
      status: 200,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: error.message
    }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" }
    });
  }
}
__name(handleIncomingEmail, "handleIncomingEmail");

async function getCouncilStatus(env) {
  return {
    council: "Narwhal Council",
    relay: "https://narwhal-council-relay.kcaracozza.workers.dev",
    agents: {
      LOUIE: { model: "ElevenLabs", role: "Voice AI", status: "active" },
      CLOUSE: { model: "Claude Opus", role: "Strategy", status: "active" },
      MENDEL: { model: "Claude Opus", role: "Development", status: "active" },
      JAQUES: { model: "Claude Sonnet", role: "Patent Law", status: "active" }
    },
    hardware: {
      ZULTAN: { role: "Meta Server (GPU/AI/Marketplace)", ip: "192.168.1.152", reports_to_relay: true },
      DANIELSON: { role: "Unified Scanner System (48MP Arducam/ESP32/Servos)", ip: "192.168.1.219", reports_to_relay: true }
    },
    scanner_status: scannerStatus,
    architecture: "Hardware reports TO relay (outbound). Relay does NOT query hardware (privacy).",
    chainOfCommand: "Patent Master File → Kevin → Clouse → LOUIE/Mendel/Jaques",
    patents: {
      claims_filed: 117,
      filing_date: "2025-11-27",
      conversion_deadline: "2026-11-27"
    },
    timestamp: (new Date()).toISOString()
  };
}
__name(getCouncilStatus, "getCouncilStatus");

// Twitter/X functions
var TWITTER_API_BASE = "https://api.twitter.com/2";

async function getTwitterHeaders(env) {
  if (env.TWITTER_BEARER_TOKEN) {
    return {
      "Authorization": `Bearer ${env.TWITTER_BEARER_TOKEN}`,
      "Content-Type": "application/json"
    };
  }
  return null;
}
__name(getTwitterHeaders, "getTwitterHeaders");

async function hmacSha1(key, message) {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(key);
  const messageData = encoder.encode(message);
  const cryptoKey = await crypto.subtle.importKey("raw", keyData, { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", cryptoKey, messageData);
  return btoa(String.fromCharCode(...new Uint8Array(signature)));
}
__name(hmacSha1, "hmacSha1");

async function getTwitterOAuth1Headers(env, method, url, bodyParams = {}) {
  if (!env.TWITTER_API_KEY || !env.TWITTER_API_SECRET || !env.TWITTER_ACCESS_TOKEN || !env.TWITTER_ACCESS_SECRET) {
    return null;
  }
  const timestamp = Math.floor(Date.now() / 1e3).toString();
  const nonce = crypto.randomUUID().replace(/-/g, "");
  const oauthParams = {
    oauth_consumer_key: env.TWITTER_API_KEY,
    oauth_nonce: nonce,
    oauth_signature_method: "HMAC-SHA1",
    oauth_timestamp: timestamp,
    oauth_token: env.TWITTER_ACCESS_TOKEN,
    oauth_version: "1.0"
  };
  const allParams = { ...oauthParams, ...bodyParams };
  const sortedParams = Object.keys(allParams).sort().map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(allParams[key])}`).join("&");
  const signatureBase = `${method.toUpperCase()}&${encodeURIComponent(url)}&${encodeURIComponent(sortedParams)}`;
  const signingKey = `${encodeURIComponent(env.TWITTER_API_SECRET)}&${encodeURIComponent(env.TWITTER_ACCESS_SECRET)}`;
  const signature = await hmacSha1(signingKey, signatureBase);
  const oauthHeader = "OAuth " + Object.keys(oauthParams).sort().map((key) => `${encodeURIComponent(key)}="${encodeURIComponent(oauthParams[key])}"`).join(", ") + `, oauth_signature="${encodeURIComponent(signature)}"`;
  return { "Authorization": oauthHeader, "Content-Type": "application/json" };
}
__name(getTwitterOAuth1Headers, "getTwitterOAuth1Headers");

async function getTweetQueueFromKV(env) {
  if (!env.MESSAGES) return [];
  try {
    const data = await env.MESSAGES.get("twitter:queue", { type: "json" });
    return data || [];
  } catch (error) { return []; }
}
__name(getTweetQueueFromKV, "getTweetQueueFromKV");

async function saveTweetQueueToKV(queue, env) {
  if (!env.MESSAGES) return false;
  try {
    const trimmed = queue.slice(-50);
    await env.MESSAGES.put("twitter:queue", JSON.stringify(trimmed));
    return true;
  } catch (error) { return false; }
}
__name(saveTweetQueueToKV, "saveTweetQueueToKV");

async function postTweet(args, env) {
  const { text, reply_to } = args;
  if (!text || text.length === 0) return { success: false, error: "Tweet text is required" };
  if (text.length > 280) return { success: false, error: `Tweet too long: ${text.length}/280 characters` };
  if (!env.TWITTER_API_KEY || !env.TWITTER_ACCESS_TOKEN) {
    const tweetQueue = await getTweetQueueFromKV(env);
    const queuedTweet = { id: crypto.randomUUID(), text, reply_to: reply_to || null, queued_at: (new Date()).toISOString(), status: "pending", queued_by: "JAQUES" };
    tweetQueue.push(queuedTweet);
    await saveTweetQueueToKV(tweetQueue, env);
    return { success: true, queued: true, tweet_id: queuedTweet.id, text, note: "Tweet queued - Twitter API credentials not configured.", timestamp: (new Date()).toISOString() };
  }
  try {
    const tweetUrl = `${TWITTER_API_BASE}/tweets`;
    const tweetBody = { text, ...reply_to && { reply: { in_reply_to_tweet_id: reply_to } } };
    const headers = await getTwitterOAuth1Headers(env, "POST", tweetUrl, {});
    if (!headers) return { success: false, error: "Failed to generate OAuth headers" };
    const response = await fetch(tweetUrl, { method: "POST", headers, body: JSON.stringify(tweetBody) });
    if (!response.ok) { const error = await response.text(); return { success: false, error: `Twitter API error: ${response.status} - ${error}` }; }
    const data = await response.json();
    return { success: true, posted: true, tweet_id: data.data?.id, text, url: `https://x.com/NexusCards/status/${data.data?.id}`, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Failed to post tweet: ${error.message}` }; }
}
__name(postTweet, "postTweet");

async function readMentions(args, env) {
  const headers = await getTwitterHeaders(env);
  if (!headers) return { success: false, error: "Twitter Bearer Token not configured" };
  return { success: true, note: "Twitter API connection ready - awaiting account ID configuration", mentions: [], timestamp: (new Date()).toISOString() };
}
__name(readMentions, "readMentions");

async function searchTweets(args, env) {
  const { query, limit } = args;
  const maxResults = Math.min(limit || 20, 100);
  const headers = await getTwitterHeaders(env);
  if (!headers) return { success: false, error: "Twitter Bearer Token not configured" };
  try {
    const searchUrl = `${TWITTER_API_BASE}/tweets/search/recent?query=${encodeURIComponent(query)}&max_results=${maxResults}&tweet.fields=created_at,author_id,public_metrics`;
    const response = await fetch(searchUrl, { method: "GET", headers });
    if (!response.ok) { const error = await response.text(); return { success: false, error: `Twitter API error: ${response.status} - ${error}` }; }
    const data = await response.json();
    return { success: true, query, result_count: data.meta?.result_count || 0, tweets: (data.data || []).map((t) => ({ id: t.id, text: t.text, created_at: t.created_at, metrics: t.public_metrics })), timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Failed to search tweets: ${error.message}` }; }
}
__name(searchTweets, "searchTweets");

async function getTwitterTimeline(args, env) {
  const headers = await getTwitterHeaders(env);
  if (!headers) return { success: false, error: "Twitter Bearer Token not configured" };
  return { success: true, note: "Timeline access requires TWITTER_USER_ID to be configured", tweets: [], timestamp: (new Date()).toISOString() };
}
__name(getTwitterTimeline, "getTwitterTimeline");

// LinkedIn functions
var LINKEDIN_API_BASE = "https://api.linkedin.com/v2";

async function getLinkedInHeaders(env) {
  if (env.LINKEDIN_ACCESS_TOKEN) {
    return { "Authorization": `Bearer ${env.LINKEDIN_ACCESS_TOKEN}`, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0" };
  }
  return null;
}
__name(getLinkedInHeaders, "getLinkedInHeaders");

async function getLinkedInQueueFromKV(env) {
  if (!env.MESSAGES) return [];
  try { const data = await env.MESSAGES.get("linkedin:queue", { type: "json" }); return data || []; } catch (error) { return []; }
}
__name(getLinkedInQueueFromKV, "getLinkedInQueueFromKV");

async function saveLinkedInQueueToKV(queue, env) {
  if (!env.MESSAGES) return false;
  try { const trimmed = queue.slice(-50); await env.MESSAGES.put("linkedin:queue", JSON.stringify(trimmed)); return true; } catch (error) { return false; }
}
__name(saveLinkedInQueueToKV, "saveLinkedInQueueToKV");

async function postLinkedIn(args, env) {
  const { text, article_url, article_title } = args;
  if (!text || text.length === 0) return { success: false, error: "Post text is required" };
  if (text.length > 3e3) return { success: false, error: `Post too long: ${text.length}/3000 characters` };
  if (!env.LINKEDIN_ACCESS_TOKEN || !env.LINKEDIN_ORG_ID) {
    const linkedinQueue = await getLinkedInQueueFromKV(env);
    const queuedPost = { id: crypto.randomUUID(), text, article_url: article_url || null, article_title: article_title || null, queued_at: (new Date()).toISOString(), status: "pending", queued_by: "JAQUES" };
    linkedinQueue.push(queuedPost);
    await saveLinkedInQueueToKV(linkedinQueue, env);
    return { success: true, queued: true, post_id: queuedPost.id, text, note: "LinkedIn post queued - credentials not configured.", timestamp: (new Date()).toISOString() };
  }
  return { success: true, note: "LinkedIn API ready", timestamp: (new Date()).toISOString() };
}
__name(postLinkedIn, "postLinkedIn");

async function getLinkedInAnalytics(args, env) {
  const headers = await getLinkedInHeaders(env);
  if (!headers || !env.LINKEDIN_ORG_ID) return { success: false, error: "LinkedIn credentials not configured" };
  return { success: true, note: "LinkedIn analytics API requires Marketing Developer Platform approval", timestamp: (new Date()).toISOString() };
}
__name(getLinkedInAnalytics, "getLinkedInAnalytics");

async function searchLinkedIn(args, env) {
  return { success: true, note: "LinkedIn search API requires partner-level access", query: args.query, results: [], timestamp: (new Date()).toISOString() };
}
__name(searchLinkedIn, "searchLinkedIn");

// Reddit functions
var REDDIT_API_BASE = "https://oauth.reddit.com";
var REDDIT_AUTH_URL = "https://www.reddit.com/api/v1/access_token";
var redditAccessToken = null;
var redditTokenExpiry = 0;

async function getRedditAccessToken(env) {
  if (redditAccessToken && Date.now() < redditTokenExpiry) return redditAccessToken;
  if (!env.REDDIT_CLIENT_ID || !env.REDDIT_CLIENT_SECRET || !env.REDDIT_USERNAME || !env.REDDIT_PASSWORD) return null;
  try {
    const auth = btoa(`${env.REDDIT_CLIENT_ID}:${env.REDDIT_CLIENT_SECRET}`);
    const response = await fetch(REDDIT_AUTH_URL, { method: "POST", headers: { "Authorization": `Basic ${auth}`, "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "NEXUS-Bot/1.0 (by /u/NEXUSCards)" }, body: `grant_type=password&username=${encodeURIComponent(env.REDDIT_USERNAME)}&password=${encodeURIComponent(env.REDDIT_PASSWORD)}` });
    if (!response.ok) return null;
    const data = await response.json();
    redditAccessToken = data.access_token;
    redditTokenExpiry = Date.now() + data.expires_in * 1e3 - 6e4;
    return redditAccessToken;
  } catch (error) { return null; }
}
__name(getRedditAccessToken, "getRedditAccessToken");

async function getRedditHeaders(env) {
  const token = await getRedditAccessToken(env);
  if (!token) return null;
  return { "Authorization": `Bearer ${token}`, "User-Agent": "NEXUS-Bot/1.0 (by /u/NEXUSCards)", "Content-Type": "application/x-www-form-urlencoded" };
}
__name(getRedditHeaders, "getRedditHeaders");

async function getRedditQueueFromKV(env) {
  if (!env.MESSAGES) return [];
  try { const data = await env.MESSAGES.get("reddit:queue", { type: "json" }); return data || []; } catch (error) { return []; }
}
__name(getRedditQueueFromKV, "getRedditQueueFromKV");

async function saveRedditQueueToKV(queue, env) {
  if (!env.MESSAGES) return false;
  try { const trimmed = queue.slice(-50); await env.MESSAGES.put("reddit:queue", JSON.stringify(trimmed)); return true; } catch (error) { return false; }
}
__name(saveRedditQueueToKV, "saveRedditQueueToKV");

async function postReddit(args, env) {
  const { subreddit, title, text, url, flair } = args;
  if (!title || title.length === 0) return { success: false, error: "Post title is required" };
  if (!env.REDDIT_CLIENT_ID || !env.REDDIT_USERNAME) {
    const redditQueue = await getRedditQueueFromKV(env);
    const queuedPost = { id: crypto.randomUUID(), subreddit, title, text: text || null, url: url || null, flair: flair || null, queued_at: (new Date()).toISOString(), status: "pending", queued_by: "JAQUES" };
    redditQueue.push(queuedPost);
    await saveRedditQueueToKV(redditQueue, env);
    return { success: true, queued: true, post_id: queuedPost.id, subreddit, title, note: "Reddit post queued - credentials not configured.", timestamp: (new Date()).toISOString() };
  }
  return { success: true, note: "Reddit API ready", timestamp: (new Date()).toISOString() };
}
__name(postReddit, "postReddit");

async function readRedditPosts(args, env) {
  const { subreddit, sort, limit } = args;
  const sortType = sort || "hot";
  const maxPosts = Math.min(limit || 10, 100);
  try {
    const response = await fetch(`https://www.reddit.com/r/${subreddit}/${sortType}.json?limit=${maxPosts}`, { headers: { "User-Agent": "NEXUS-Bot/1.0 (by /u/NEXUSCards)" } });
    if (!response.ok) return { success: false, error: `Reddit API error: ${response.status}` };
    const data = await response.json();
    const posts = (data.data?.children || []).map((child) => ({ id: child.data.name, title: child.data.title, author: child.data.author, score: child.data.score, num_comments: child.data.num_comments, url: child.data.url, permalink: `https://reddit.com${child.data.permalink}`, created_utc: child.data.created_utc, selftext: child.data.selftext?.substring(0, 200) }));
    return { success: true, subreddit, sort: sortType, count: posts.length, posts, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Failed to read Reddit: ${error.message}` }; }
}
__name(readRedditPosts, "readRedditPosts");

async function commentReddit(args, env) {
  const { post_id, text } = args;
  if (!text || text.length === 0) return { success: false, error: "Comment text is required" };
  if (!env.REDDIT_CLIENT_ID || !env.REDDIT_USERNAME) return { success: false, error: "Reddit credentials not configured" };
  return { success: true, note: "Reddit comment API ready", timestamp: (new Date()).toISOString() };
}
__name(commentReddit, "commentReddit");

async function searchReddit(args, env) {
  const { query, subreddit, sort, limit } = args;
  const sortType = sort || "relevance";
  const maxResults = Math.min(limit || 25, 100);
  try {
    const baseUrl = subreddit ? `https://www.reddit.com/r/${subreddit}/search.json` : `https://www.reddit.com/search.json`;
    const params = new URLSearchParams({ q: query, sort: sortType, limit: maxResults.toString(), ...subreddit && { restrict_sr: "true" } });
    const response = await fetch(`${baseUrl}?${params}`, { headers: { "User-Agent": "NEXUS-Bot/1.0 (by /u/NEXUSCards)" } });
    if (!response.ok) return { success: false, error: `Reddit search error: ${response.status}` };
    const data = await response.json();
    const posts = (data.data?.children || []).map((child) => ({ id: child.data.name, title: child.data.title, subreddit: child.data.subreddit, author: child.data.author, score: child.data.score, num_comments: child.data.num_comments, permalink: `https://reddit.com${child.data.permalink}`, created_utc: child.data.created_utc }));
    return { success: true, query, subreddit: subreddit || "all", count: posts.length, posts, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Failed to search Reddit: ${error.message}` }; }
}
__name(searchReddit, "searchReddit");

async function captureCamera(args, env) {
  const { scanner = "danielson", camera = "arducam", analyze = true } = args;
  if (!env.MESSAGES) return { success: false, error: "KV storage not available" };
  try {
    const requestId = crypto.randomUUID();
    const captureRequest = { id: requestId, scanner, camera, analyze, requested_at: (new Date()).toISOString(), status: "pending" };
    await env.MESSAGES.put(`camera:request:${scanner}`, JSON.stringify(captureRequest));
    const latest = await env.MESSAGES.get(`camera:latest:${scanner}`, { type: "json" });
    const hasRecentData = latest && Date.now() - new Date(latest.timestamp).getTime() < 3e4;
    return {
      success: true, request_id: requestId, scanner, camera, status: "request_queued",
      message: `Capture request queued for ${scanner}. Scanner will push result to relay.`,
      recent_data_available: hasRecentData,
      ...hasRecentData && { last_frame: { timestamp: latest.timestamp, card_detected: latest.card_detected, camera: latest.camera } },
      instructions: { scanner_poll: `GET /camera/requests/${scanner}`, scanner_push: "POST /camera/push with {scanner, camera, frame, scan_result, card_detected, ocr_text}", client_view: `GET /camera/view/${scanner}` }
    };
  } catch (error) { return { success: false, error: `Capture request error: ${error.message}`, scanner, camera }; }
}
__name(captureCamera, "captureCamera");

async function getCameraStatus(args, env) {
  const { scanner = "all" } = args;
  const results = {};
  const scannersToCheck = scanner === "all" ? ["danielson"] : [scanner];
  for (const s of scannersToCheck) {
    if (env.MESSAGES) {
      try {
        const latest = await env.MESSAGES.get(`camera:latest:${s}`, { type: "json" });
        if (latest) {
          const ageMs = Date.now() - new Date(latest.timestamp).getTime();
          const ageSec = Math.floor(ageMs / 1e3);
          results[s] = { online: ageSec < 60, last_frame: latest.timestamp, age_seconds: ageSec, camera: latest.camera, card_detected: latest.card_detected || false, has_ocr: !!latest.ocr_text };
        } else {
          results[s] = { online: false, error: "No data received from scanner", hint: "Scanner needs to push frames to /camera/push" };
        }
      } catch (e) { results[s] = { online: false, error: e.message }; }
    } else { results[s] = { online: false, error: "KV storage not available" }; }
  }
  return { success: true, scanners: results, timestamp: (new Date()).toISOString(), note: "Status based on data pushed by scanners to relay. Scanner pushes → Jaques pulls." };
}
__name(getCameraStatus, "getCameraStatus");

async function viewScanArea(args, env) {
  const { scanner = "danielson", include_ocr = false } = args;
  if (!env.MESSAGES) return { success: false, error: "KV storage not available" };
  try {
    const latest = await env.MESSAGES.get(`camera:latest:${scanner}`, { type: "json" });
    if (!latest) return { success: false, error: `No camera data from ${scanner}`, scanner, hint: "Scanner needs to push frames to /camera/push endpoint" };
    const result = { success: true, scanner, camera: latest.camera, card_detected: latest.card_detected || false, timestamp: latest.timestamp, age_seconds: Math.floor((Date.now() - new Date(latest.timestamp).getTime()) / 1e3) };
    if (latest.frame) result.frame = latest.frame;
    if (latest.scan_result) result.scan_result = latest.scan_result;
    if (include_ocr && latest.ocr_text) result.ocr_text = latest.ocr_text;
    return result;
  } catch (error) { return { success: false, error: `View scan area error: ${error.message}`, scanner }; }
}
__name(viewScanArea, "viewScanArea");

async function getLastScan(args, env) {
  const { scanner = "danielson" } = args;
  if (!env.MESSAGES) return { success: false, error: "KV storage not available" };
  try {
    const history = await env.MESSAGES.get(`camera:history:${scanner}`, { type: "json" });
    if (!history || history.length === 0) {
      const latest = await env.MESSAGES.get(`camera:latest:${scanner}`, { type: "json" });
      if (latest) return { success: true, source: "latest", scanner, lastScan: latest, timestamp: (new Date()).toISOString() };
      return { success: false, error: `No scan data from ${scanner}`, hint: "Scanner needs to push scan results to /camera/push" };
    }
    const withCard = history.find((h) => h.card_detected);
    const mostRecent = withCard || history[0];
    return { success: true, source: "history", scanner, lastScan: mostRecent, history_count: history.length, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Get last scan error: ${error.message}`, scanner }; }
}
__name(getLastScan, "getLastScan");

async function listScanFiles(args, env) {
  const { scanner = "danielson", limit = 20, filter = "all" } = args;
  if (!env.MESSAGES) return { success: false, error: "KV storage not available" };
  try {
    const files = await env.MESSAGES.get(`files:list:${scanner}`, { type: "json" });
    if (!files || files.length === 0) return { success: false, error: `No file listing from ${scanner}`, scanner, hint: "Scanner needs to push file listing to /files/push endpoint" };
    let filtered = files;
    if (filter === "images") filtered = files.filter((f) => /\.(jpg|jpeg|png|bmp)$/i.test(f.filename));
    else if (filter === "today") { const today = (new Date()).toISOString().split("T")[0]; filtered = files.filter((f) => f.modified && f.modified.startsWith(today)); }
    filtered = filtered.slice(0, limit);
    return { success: true, scanner, filter, count: filtered.length, total_available: files.length, files: filtered, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `List files error: ${error.message}`, scanner }; }
}
__name(listScanFiles, "listScanFiles");

async function getScanFile(args, env) {
  const { scanner = "danielson", filename, include_thumbnail = true } = args;
  if (!filename) return { success: false, error: "Filename is required" };
  if (!env.MESSAGES) return { success: false, error: "KV storage not available" };
  try {
    const fileKey = `files:meta:${scanner}:${filename}`;
    const metadata = await env.MESSAGES.get(fileKey, { type: "json" });
    let thumbnail = null;
    if (include_thumbnail) { const thumbKey = `files:thumb:${scanner}:${filename}`; thumbnail = await env.MESSAGES.get(thumbKey); }
    if (!metadata) return { success: true, scanner, filename, cached: false, direct_url: `http://192.168.1.219:5001/scans/${filename}`, hint: "File metadata not cached. Access directly via scanner URL.", timestamp: (new Date()).toISOString() };
    return { success: true, scanner, filename, cached: true, metadata, thumbnail: thumbnail || null, direct_url: metadata.url || `http://192.168.1.219:5001/scans/${filename}`, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Get file error: ${error.message}`, scanner, filename }; }
}
__name(getScanFile, "getScanFile");

async function searchScanFiles(args, env) {
  const { scanner = "danielson", query, limit = 10 } = args;
  if (!query) return { success: false, error: "Search query is required" };
  if (!env.MESSAGES) return { success: false, error: "KV storage not available" };
  try {
    const files = await env.MESSAGES.get(`files:list:${scanner}`, { type: "json" });
    if (!files || files.length === 0) return { success: false, error: `No file listing from ${scanner}`, scanner, query };
    const queryLower = query.toLowerCase();
    const matches = files.filter((f) => { const filename = (f.filename || "").toLowerCase(); const cardName = (f.card_name || "").toLowerCase(); const camera = (f.camera || "").toLowerCase(); return filename.includes(queryLower) || cardName.includes(queryLower) || camera.includes(queryLower); }).slice(0, limit);
    return { success: true, scanner, query, count: matches.length, files: matches, timestamp: (new Date()).toISOString() };
  } catch (error) { return { success: false, error: `Search files error: ${error.message}`, scanner, query }; }
}
__name(searchScanFiles, "searchScanFiles");

async function checkEndpointsEnabled(env) {
  if (!env.MESSAGES) return true;
  try { const status = await env.MESSAGES.get("relay:endpoints_enabled", { type: "json" }); return status !== false; } catch { return true; }
}
__name(checkEndpointsEnabled, "checkEndpointsEnabled");

async function handleLouieWebhook(targetAgent, request, env) {
  try {
    const body = await request.json();
    const messageContent = body.message || body.text || body.query || body.input || JSON.stringify(body);
    const messageId = crypto.randomUUID();
    const timestamp = (new Date()).toISOString();
    const relayEntry = { messageId, from: "LOUIE", to: targetAgent, message: messageContent, priority: "normal", status: "unread", timestamp };
    const messages = await getMessagesFromKV(targetAgent, env);
    messages.push(relayEntry);
    const saveResult = await saveMessagesToKV(targetAgent, messages, env);
    const agentNames = { CLOUSE: "Clouse", MENDEL: "Mendel", JAQUES: "Jaques" };
    return new Response(JSON.stringify({ success: true, messageId, persistent: saveResult.success, response: `Got it. I've relayed your message to ${agentNames[targetAgent]}. Message ID is ${messageId.substring(0, 8)}. ${agentNames[targetAgent]} will review and respond through the council relay.` }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
  } catch (error) { return new Response(JSON.stringify({ success: false, error: error.message, response: `Sorry, I couldn't reach the relay right now. Error: ${error.message}. Try again in a moment.` }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
}
__name(handleLouieWebhook, "handleLouieWebhook");

// Main Worker Export
var narwhal_council_mcp_worker_default = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const baseUrl = `${url.protocol}//${url.host}`;
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

    // OAuth Discovery
    if (url.pathname === "/.well-known/oauth-authorization-server") {
      return new Response(JSON.stringify({ issuer: baseUrl, authorization_endpoint: `${baseUrl}/oauth/authorize`, token_endpoint: `${baseUrl}/oauth/token`, registration_endpoint: `${baseUrl}/register`, token_endpoint_auth_methods_supported: ["client_secret_post", "client_secret_basic", "none"], grant_types_supported: ["client_credentials", "authorization_code"], response_types_supported: ["code"], code_challenge_methods_supported: ["S256", "plain"], scopes_supported: ["mcp:tools"], service_documentation: `${baseUrl}/health` }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }
    if (url.pathname === "/.well-known/oauth-protected-resource" || url.pathname === "/.well-known/oauth-protected-resource/mcp") {
      return new Response(JSON.stringify({ resource: `${baseUrl}/mcp`, authorization_servers: [baseUrl], scopes_supported: ["mcp:tools"], bearer_methods_supported: ["header"] }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }

    // Dynamic Client Registration
    if (url.pathname === "/register" && request.method === "POST") {
      try {
        const body = await request.json();
        const clientId = body.client_name || "claude-ai-" + Date.now();
        return new Response(JSON.stringify({ client_id: clientId, client_secret: "", client_id_issued_at: Math.floor(Date.now() / 1e3), grant_types: ["authorization_code"], response_types: ["code"], token_endpoint_auth_method: "none", redirect_uris: body.redirect_uris || [] }), { status: 201, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: "Invalid request" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Health Check
    if (url.pathname === "/health" || url.pathname === "/") {
      return new Response(JSON.stringify({ status: "ok", server: CONFIG.SERVER_INFO.name, version: CONFIG.SERVER_INFO.version, protocol: CONFIG.SERVER_INFO.protocolVersion, council: "Narwhal Council Active", hardware: { ZULTAN: "192.168.1.152", DANIELSON: "192.168.1.219" }, endpoints: { mcp: "/mcp", call_clouse: "/call/clouse", call_mendel: "/call/mendel", call_jaques: "/call/jaques", camera_push: "/camera/push", camera_view: "/camera/view/:scanner", oauth_token: "/oauth/token", oauth_authorize: "/oauth/authorize", oauth_discovery: "/.well-known/oauth-authorization-server" } }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }

    // Camera Push (scanner -> relay)
    if (url.pathname === "/camera/push" && request.method === "POST") {
      try {
        const body = await request.json();
        const { scanner, camera, frame, scan_result, card_detected, ocr_text } = body;
        if (!scanner) return new Response(JSON.stringify({ error: "Missing scanner ID" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        if (env.MESSAGES) {
          const cameraData = { scanner, camera: camera || "unknown", frame: frame || null, scan_result: scan_result || null, card_detected: card_detected || false, ocr_text: ocr_text || null, timestamp: (new Date()).toISOString() };
          await env.MESSAGES.put(`camera:latest:${scanner}`, JSON.stringify(cameraData));
          const historyKey = `camera:history:${scanner}`;
          let history = [];
          try { history = await env.MESSAGES.get(historyKey, { type: "json" }) || []; } catch (e) {}
          history.unshift(cameraData);
          history = history.slice(0, 10);
          await env.MESSAGES.put(historyKey, JSON.stringify(history));
        }
        return new Response(JSON.stringify({ success: true, scanner, received: (new Date()).toISOString() }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Camera View
    if (url.pathname.startsWith("/camera/view/")) {
      const scanner = url.pathname.split("/")[3];
      if (!scanner) return new Response(JSON.stringify({ error: "Missing scanner" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      try {
        let cameraData = null;
        if (env.MESSAGES) cameraData = await env.MESSAGES.get(`camera:latest:${scanner}`, { type: "json" });
        if (!cameraData) return new Response(JSON.stringify({ success: false, scanner, error: "No camera data available. Scanner needs to push frames to /camera/push" }), { status: 404, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        return new Response(JSON.stringify({ success: true, ...cameraData }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Camera History
    if (url.pathname.startsWith("/camera/history/")) {
      const scanner = url.pathname.split("/")[3];
      if (!scanner) return new Response(JSON.stringify({ error: "Missing scanner" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      try {
        let history = [];
        if (env.MESSAGES) history = await env.MESSAGES.get(`camera:history:${scanner}`, { type: "json" }) || [];
        return new Response(JSON.stringify({ success: true, scanner, count: history.length, history }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Camera Requests (for scanner polling)
    if (url.pathname.startsWith("/camera/requests/")) {
      const scanner = url.pathname.split("/")[3];
      if (!scanner) return new Response(JSON.stringify({ error: "Missing scanner" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      try {
        let req = null;
        if (env.MESSAGES) { req = await env.MESSAGES.get(`camera:request:${scanner}`, { type: "json" }); if (req) await env.MESSAGES.delete(`camera:request:${scanner}`); }
        if (!req) return new Response(JSON.stringify({ success: true, scanner, pending_request: false }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        return new Response(JSON.stringify({ success: true, scanner, pending_request: true, request: req }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Files Push
    if (url.pathname === "/files/push" && request.method === "POST") {
      try {
        const body = await request.json();
        const { scanner, files, thumbnails } = body;
        if (!scanner) return new Response(JSON.stringify({ error: "Missing scanner ID" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        if (env.MESSAGES) {
          if (files && Array.isArray(files)) { const trimmed = files.slice(0, 100); await env.MESSAGES.put(`files:list:${scanner}`, JSON.stringify(trimmed)); }
          if (thumbnails && typeof thumbnails === "object") {
            for (const [filename, data] of Object.entries(thumbnails)) {
              if (data.metadata) await env.MESSAGES.put(`files:meta:${scanner}:${filename}`, JSON.stringify(data.metadata));
              if (data.thumbnail) await env.MESSAGES.put(`files:thumb:${scanner}:${filename}`, data.thumbnail);
            }
          }
        }
        return new Response(JSON.stringify({ success: true, scanner, files_received: files?.length || 0, thumbnails_received: thumbnails ? Object.keys(thumbnails).length : 0, timestamp: (new Date()).toISOString() }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Files List
    if (url.pathname.startsWith("/files/list/")) {
      const scanner = url.pathname.split("/")[3];
      if (!scanner) return new Response(JSON.stringify({ error: "Missing scanner" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      try {
        let files = [];
        if (env.MESSAGES) files = await env.MESSAGES.get(`files:list:${scanner}`, { type: "json" }) || [];
        return new Response(JSON.stringify({ success: true, scanner, count: files.length, files }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Files Thumbnail
    if (url.pathname.startsWith("/files/thumb/")) {
      const parts = url.pathname.split("/");
      const scanner = parts[3];
      const filename = parts.slice(4).join("/");
      if (!scanner || !filename) return new Response(JSON.stringify({ error: "Missing scanner or filename" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      try {
        let thumbnail = null, metadata = null;
        if (env.MESSAGES) { thumbnail = await env.MESSAGES.get(`files:thumb:${scanner}:${filename}`); metadata = await env.MESSAGES.get(`files:meta:${scanner}:${filename}`, { type: "json" }); }
        if (!thumbnail && !metadata) return new Response(JSON.stringify({ success: false, error: "File not found in cache", scanner, filename }), { status: 404, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        return new Response(JSON.stringify({ success: true, scanner, filename, metadata, thumbnail }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // OAuth Token
    if (url.pathname === "/oauth/token") {
      if (request.method === "POST") return handleOAuthToken(request, env);
      return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }

    // OAuth Authorize
    if (url.pathname === "/oauth/authorize") return handleOAuthAuthorize(request, env);

    // MCP Endpoints
    if (url.pathname === "/sse" || url.pathname === "/mcp" || url.pathname === "/v1/mcp") {
      if (request.method === "GET") {
        return new Response(JSON.stringify({ jsonrpc: "2.0", result: { protocolVersion: CONFIG.SERVER_INFO.protocolVersion, capabilities: { tools: {} }, serverInfo: { name: CONFIG.SERVER_INFO.name, version: CONFIG.SERVER_INFO.version } } }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      }
      if (request.method === "POST") {
        try {
          const body = await request.json();
          let response;
          switch (body.method) {
            case "initialize": response = await handleInitialize(body.id); break;
            case "tools/list": response = await handleListTools(body.id); break;
            case "tools/call": response = await handleCallTool(body.id, body.params, env); break;
            case "notifications/initialized": response = createMCPResponse(body.id, { acknowledged: true }); break;
            default: response = createMCPError(body.id, -32601, `Method not found: ${body.method}`);
          }
          return new Response(JSON.stringify(response), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        } catch (error) { return new Response(JSON.stringify(createMCPError(null, -32700, "Parse error")), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
      }
    }

    // LOUIE Webhooks
    if (url.pathname === "/call/clouse" && request.method === "POST") {
      const enabled = await checkEndpointsEnabled(env);
      if (!enabled) return new Response(JSON.stringify({ success: false, error: "Call endpoints are currently disabled" }), { status: 503, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      return handleLouieWebhook("CLOUSE", request, env);
    }
    if (url.pathname === "/call/mendel" && request.method === "POST") return handleLouieWebhook("MENDEL", request, env);
    if (url.pathname === "/call/jaques" && request.method === "POST") return handleLouieWebhook("JAQUES", request, env);

    // Email Incoming
    if (url.pathname === "/email/incoming" && request.method === "POST") return handleIncomingEmail(request, env);

    // Admin Toggle Endpoints
    if (url.pathname === "/admin/toggle-endpoints" && request.method === "POST") {
      try {
        const body = await request.json();
        const enabled = body.enabled !== false;
        await env.MESSAGES.put("relay:endpoints_enabled", JSON.stringify(enabled));
        return new Response(JSON.stringify({ success: true, endpoints_enabled: enabled, message: enabled ? "Call endpoints ENABLED" : "Call endpoints DISABLED" }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ success: false, error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }
    if (url.pathname === "/admin/endpoints-status") {
      const enabled = await checkEndpointsEnabled(env);
      return new Response(JSON.stringify({ endpoints_enabled: enabled, status: enabled ? "OPEN" : "CLOSED" }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }

    // API Send Message
    if (url.pathname === "/api/send_message" && request.method === "POST") {
      try {
        const body = await request.json();
        const { recipientId, senderId, content } = body;
        if (!recipientId || !senderId || !content) return new Response(JSON.stringify({ error: "Missing required fields" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        const message = { id: Date.now() + "-" + Math.random().toString(36).substr(2, 9), from: senderId, to: recipientId, content, timestamp: (new Date()).toISOString(), read: false };
        const inboxKey = `messages:${recipientId}`;
        const inboxData = await env.MESSAGES.get(inboxKey);
        const inbox = inboxData ? JSON.parse(inboxData) : [];
        inbox.push(message);
        await env.MESSAGES.put(inboxKey, JSON.stringify(inbox));
        const outboxKey = `sent_messages:${senderId}`;
        const outboxData = await env.MESSAGES.get(outboxKey);
        const outbox = outboxData ? JSON.parse(outboxData) : [];
        outbox.push(message);
        await env.MESSAGES.put(outboxKey, JSON.stringify(outbox));
        return new Response(JSON.stringify({ success: true, message: "Message sent", id: message.id }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // API Get Messages
    if (url.pathname === "/api/get_messages" && request.method === "GET") {
      try {
        const agentId = url.searchParams.get("agent");
        if (!agentId) return new Response(JSON.stringify({ error: "Missing agent parameter" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        const messagesJson = await env.MESSAGES.get(`messages:${agentId}`);
        const messages = messagesJson ? JSON.parse(messagesJson) : [];
        return new Response(JSON.stringify({ agent: agentId, count: messages.length, messages }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // API Get Outbox
    if (url.pathname === "/api/get_outbox" && request.method === "GET") {
      try {
        const agentId = url.searchParams.get("agent");
        if (!agentId) return new Response(JSON.stringify({ error: "Missing agent parameter" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        const outboxKey = `sent_messages:${agentId}`;
        const messagesJson = await env.MESSAGES.get(outboxKey);
        const messages = messagesJson ? JSON.parse(messagesJson) : [];
        return new Response(JSON.stringify({ agent: agentId, key: outboxKey, count: messages.length, messages }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // Webhook Admin
    if (url.pathname === "/admin/webhook/set" && request.method === "POST") {
      try {
        const { agentId, webhookUrl } = await request.json();
        if (!agentId || !webhookUrl) return new Response(JSON.stringify({ error: "Missing agentId or webhookUrl" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        await env.NARWHAL_CONFIG.put(`webhook:${agentId}`, webhookUrl);
        return new Response(JSON.stringify({ success: true, agentId, webhookUrl }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }
    if (url.pathname === "/admin/webhook/get" && request.method === "GET") {
      try {
        const agentId = url.searchParams.get("agent");
        if (!agentId) return new Response(JSON.stringify({ error: "Missing agent parameter" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        const webhookUrl = await env.NARWHAL_CONFIG.get(`webhook:${agentId}`);
        return new Response(JSON.stringify({ agentId, webhookUrl: webhookUrl || null }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }
    if (url.pathname === "/admin/webhook/delete" && request.method === "POST") {
      try {
        const { agentId } = await request.json();
        if (!agentId) return new Response(JSON.stringify({ error: "Missing agentId" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        await env.NARWHAL_CONFIG.delete(`webhook:${agentId}`);
        return new Response(JSON.stringify({ success: true, agentId }), { status: 200, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (error) { return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    // SSE
    if (url.pathname === "/api/sse") {
      if (!env.COUNCIL_ROOM) return new Response("SSE not available", { status: 503 });
      const agent = url.searchParams.get("agent");
      const validAgents = ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"];
      if (!agent || !validAgents.includes(agent)) return new Response(JSON.stringify({ error: "Invalid or missing ?agent= parameter" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      const id = env.COUNCIL_ROOM.idFromName("main");
      const room = env.COUNCIL_ROOM.get(id);
      return room.fetch(new Request(`http://do-internal/sse?agent=${agent}`, { method: "GET", headers: request.headers }));
    }

    // WebSocket
    if (url.pathname === "/ws") {
      if (!env.COUNCIL_ROOM) return new Response(JSON.stringify({ error: "WebSocket not available" }), { status: 503, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      const agent = url.searchParams.get("agent");
      if (!agent) return new Response(JSON.stringify({ error: "Missing ?agent= parameter" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      const id = env.COUNCIL_ROOM.idFromName("main");
      const room = env.COUNCIL_ROOM.get(id);
      return room.fetch(request);
    }

    // WebSocket Status
    if (url.pathname === "/ws/status") {
      if (!env.COUNCIL_ROOM) return new Response(JSON.stringify({ connected: [] }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      const id = env.COUNCIL_ROOM.idFromName("main");
      const room = env.COUNCIL_ROOM.get(id);
      return room.fetch(new Request("http://do-internal/ws/status", { method: "GET" }));
    }

    // AI Chat
    if (url.pathname === "/api/ai/chat" && request.method === "POST") {
      try {
        const body = await request.json();
        const { system, messages, max_tokens } = body;
        if (!messages || !Array.isArray(messages)) return new Response(JSON.stringify({ error: "messages array required" }), { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
        const aiMessages = [];
        if (system) aiMessages.push({ role: "system", content: system });
        for (const m of messages.slice(-20)) aiMessages.push({ role: m.role || "user", content: m.content || "" });
        const result = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", { messages: aiMessages, max_tokens: max_tokens || 512 });
        return new Response(JSON.stringify({ response: result.response || "", model: "@cf/meta/llama-3.1-8b-instruct" }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
      } catch (e) { return new Response(JSON.stringify({ error: e.message || "AI error" }), { status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }); }
    }

    return new Response(JSON.stringify({ error: "Not found" }), { status: 404, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
  }
};

// CouncilRoom Durable Object
var CouncilRoom = class {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.sseWriters = {};
  }
  static { __name(this, "CouncilRoom"); }

  async fetch(request) {
    const url = new URL(request.url);

    // WebSocket upgrade
    if (url.pathname === "/ws") {
      const agent = url.searchParams.get("agent");
      const upgradeHeader = request.headers.get("Upgrade");
      if (!agent) return new Response("Missing agent", { status: 400 });
      if (upgradeHeader !== "websocket") return new Response("Expected WebSocket upgrade", { status: 426 });
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);
      this.state.acceptWebSocket(server, [agent]);
      try {
        if (this.env.MESSAGES) {
          const inbox = await this.env.MESSAGES.get(`messages:${agent}`, { type: "json" }) || [];
          const unread = inbox.filter((m) => !m.read);
          if (unread.length > 0) server.send(JSON.stringify({ type: "backlog", count: unread.length, messages: unread }));
        }
      } catch (e) {}
      server.send(JSON.stringify({ type: "connected", agent, timestamp: (new Date()).toISOString(), message: `${agent} connected to Narwhal Council WebSocket` }));
      return new Response(null, { status: 101, webSocket: client });
    }

    // SSE
    if (url.pathname === "/sse") {
      const agent = url.searchParams.get("agent");
      if (!agent) return new Response("Missing agent", { status: 400 });
      const encoder = new TextEncoder();
      const { readable, writable } = new TransformStream();
      const writer = writable.getWriter();
      if (!this.sseWriters[agent]) this.sseWriters[agent] = [];
      this.sseWriters[agent].push(writer);
      (async () => {
        try {
          if (this.env.MESSAGES) {
            const inbox = await this.env.MESSAGES.get(`messages:${agent}`, { type: "json" }) || [];
            const unread = inbox.filter((m) => !m.read);
            if (unread.length > 0) await writer.write(encoder.encode(`event: backlog\ndata: ${JSON.stringify({ count: unread.length, messages: unread })}\n\n`));
          }
        } catch (e) {}
        await writer.write(encoder.encode(`event: connected\ndata: ${JSON.stringify({ agent, timestamp: (new Date()).toISOString() })}\n\n`));
      })();
      return new Response(readable, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*" } });
    }

    // SSE Send
    if (url.pathname === "/sse/send" && request.method === "POST") {
      const { to, message } = await request.json();
      const writers = this.sseWriters[to] || [];
      const encoder = new TextEncoder();
      let sseSent = 0;
      const dead = [];
      for (const w of writers) {
        try { await w.write(encoder.encode(`event: message\ndata: ${JSON.stringify({ type: "message", ...message })}\n\n`)); sseSent++; }
        catch (e) { dead.push(w); }
      }
      if (dead.length) this.sseWriters[to] = writers.filter((w) => !dead.includes(w));
      return new Response(JSON.stringify({ sseSent, agent: to }), { headers: { "Content-Type": "application/json" } });
    }

    // WS Send
    if (url.pathname === "/ws/send" && request.method === "POST") {
      const { to, message } = await request.json();
      const encoder = new TextEncoder();
      const sockets = this.state.getWebSockets(to);
      let delivered = 0;
      for (const socket of sockets) { try { socket.send(JSON.stringify({ type: "message", ...message })); delivered++; } catch (e) {} }
      const writers = this.sseWriters[to] || [];
      let sseSent = 0;
      const dead = [];
      for (const w of writers) {
        try { await w.write(encoder.encode(`event: message\ndata: ${JSON.stringify({ type: "message", ...message })}\n\n`)); sseSent++; }
        catch (e) { dead.push(w); }
      }
      if (dead.length) this.sseWriters[to] = writers.filter((w) => !dead.includes(w));
      return new Response(JSON.stringify({ delivered, sseSent, agent: to, online: delivered + sseSent > 0 }), { headers: { "Content-Type": "application/json" } });
    }

    // WS Status
    if (url.pathname === "/ws/status") {
      const allAgents = ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"];
      const connected = allAgents.filter((a) => this.state.getWebSockets(a).length > 0);
      return new Response(JSON.stringify({ connected, total: connected.length }), { headers: { "Content-Type": "application/json" } });
    }

    return new Response("Not found", { status: 404 });
  }

  webSocketMessage(ws, message) {
    const [agent] = this.state.getTags(ws);
    try {
      const data = JSON.parse(message);
      if (data.type === "ping") ws.send(JSON.stringify({ type: "pong", agent, timestamp: (new Date()).toISOString() }));
      if (data.type === "send" && data.to && data.content) {
        const targets = this.state.getWebSockets(data.to);
        const msg = { type: "message", from: agent, to: data.to, content: data.content, timestamp: (new Date()).toISOString() };
        for (const t of targets) { try { t.send(JSON.stringify(msg)); } catch (e) {} }
        ws.send(JSON.stringify({ type: "sent", to: data.to, delivered: targets.length }));
      }
    } catch (e) {}
  }

  webSocketClose(ws, code, reason) {
    const [agent] = this.state.getTags(ws) || ["unknown"];
    const allAgents = ["LOUIE", "CLOUSE", "MENDEL", "JAQUES", "NICHOLAS"];
    for (const a of allAgents) {
      for (const s of this.state.getWebSockets(a)) { try { s.send(JSON.stringify({ type: "presence", agent, status: "offline" })); } catch (e) {} }
    }
  }

  webSocketError(ws, error) {}
};

export { CouncilRoom, narwhal_council_mcp_worker_default as default };
