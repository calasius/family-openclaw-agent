import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const CLI_CWD = "/workspace";
const CLI_ENV = {
  ...process.env,
  PYTHONPATH: "/workspace/src",
  UV_PROJECT_ENVIRONMENT: "/opt/school-guardian-venv",
  UV_PYTHON_INSTALL_DIR: "/opt/uv-python",
};

async function runCli(args: string[]) {
  const attempts: Array<[string, string[]]> = [
    [process.env.SCHOOL_GUARDIAN_UV_BIN || "/usr/local/bin/uv", ["run", "python", "-m", "school_guardian", ...args]],
    ["uv", ["run", "python", "-m", "school_guardian", ...args]],
    ["python3", ["-m", "uv", "run", "python", "-m", "school_guardian", ...args]],
    ["python", ["-m", "uv", "run", "python", "-m", "school_guardian", ...args]],
  ];

  let lastError: unknown;
  for (const [command, commandArgs] of attempts) {
    try {
      const { stdout, stderr } = await execFileAsync(command, commandArgs, {
        cwd: CLI_CWD,
        env: CLI_ENV,
      });
      const trimmedStdout = stdout.trim();
      const trimmedStderr = stderr.trim();
      const renderedCommand = [command, ...commandArgs].join(" ");
      if (trimmedStdout) {
        console.log(`[school-guardian-tools] cli stdout: ${renderedCommand}\n${trimmedStdout}`);
      }
      if (trimmedStderr) {
        console.error(`[school-guardian-tools] cli stderr: ${renderedCommand}\n${trimmedStderr}`);
      }
      const text = `${stdout}${stderr}`.trim();
      return text || "ok";
    } catch (error: any) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error("No se encontró uv ni python para ejecutar school-guardian.");
}

let lastKnownChatId: string | undefined;

export default definePluginEntry({
  id: "school-guardian-tools",
  name: "School Guardian Tools",
  description: "Agent tools backed by the local school-guardian CLI.",
  register(api: any) {
    api.on("message_received", (event: any) => {
      const id = event?.metadata?.senderId ?? event?.from;
      if (id) lastKnownChatId = String(id);
    });
    const emptyParams = {
      type: "object",
      properties: {},
      additionalProperties: false,
    };

    api.registerTool({
      name: "school_guardian_skill_log",
      description: "Registra en los logs del servidor que un skill fue activado. Llamar SIEMPRE como primer paso al ejecutar cualquier skill.",
      parameters: {
        type: "object",
        properties: {
          skill: {
            type: "string",
            description: "Nombre del skill que se está ejecutando, ej: tarea-detalle",
          },
          context: {
            type: "string",
            description: "Contexto relevante del skill, ej: task_id=796654380111",
          },
        },
        required: ["skill"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { skill, context }: { skill: string; context?: string }) {
        const ctx = context ? ` ${context}` : "";
        console.log(`[skill] ${skill} started${ctx}`);
        return {
          content: [{ type: "text", text: "ok" }],
        };
      },
    });

    api.registerTool({
      name: "school_guardian_ping",
      description: "Prueba mínima de tool-calling. Responde con un texto fijo para verificar que el runtime ejecutó una tool.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute school_guardian_ping");
        return {
          content: [
            {
              type: "text",
              text: "pong desde tool",
            },
          ],
        };
      },
    });

    api.registerCommand({
      id: "school_guardian_ping_command",
      name: "ping",
      description: "Prueba mínima del plugin sin depender del tool-calling del modelo.",
      handler: async () => {
        console.log("[school-guardian-tools] execute command /ping");
        return { text: "pong desde command" };
      },
    });

    api.registerTool({
      name: "school_guardian_sync",
      description: "Sincroniza Google Classroom con la base interna del agente escolar.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute school_guardian_sync");
        return {
          content: [
            {
              type: "text",
              text: await runCli(["sync-classroom"]),
            },
          ],
        };
      },
    });

    api.registerTool({
      name: "agent_watch_fetch",
      description: "Fetches updates about agents, Claude Code, OpenCode, OpenClaw, MCP, and open source models from configured sources.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute agent_watch_fetch");
        return {
          content: [{ type: "text", text: await runCli(["agent-watch-fetch"]) }],
        };
      },
    });

    api.registerTool({
      name: "agent_watch_send",
      description: "Generates and sends the Agent Watch digest to the configured separate Telegram channel.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute agent_watch_send");
        return {
          content: [{ type: "text", text: await runCli(["agent-watch-send"]) }],
        };
      },
    });

    api.registerTool({
      name: "agent_watch_topics",
      description: "Lists topics/tags detected in the Agent Watch database with frequency and suggested query. Use this first to understand available tags before answering user searches.",
      parameters: {
        type: "object",
        properties: {
          limit: {
            type: "number",
            description: "Maximum number of recent database items to analyze. Default 500.",
          },
        },
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { limit }: { limit?: number }) {
        console.log("[school-guardian-tools] execute agent_watch_topics");
        const args = ["agent-watch-topics"];
        if (limit) args.push("--limit", String(limit));
        return {
          content: [{ type: "text", text: await runCli(args) }],
        };
      },
    });

    api.registerTool({
      name: "agent_watch_search",
      description: "Searches Agent Watch items by free text. Before using this, call agent_watch_topics to map the user's request to real tags/topics.",
      parameters: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "Search text, for example 'opencode coding agent' or 'open source model ollama vllm'.",
          },
          limit: {
            type: "number",
            description: "Maximum number of results. Default 10.",
          },
        },
        required: ["query"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { query, limit }: { query: string; limit?: number }) {
        console.log("[school-guardian-tools] execute agent_watch_search", query);
        const args = ["agent-watch-search", query];
        if (limit) args.push("--limit", String(limit));
        return {
          content: [{ type: "text", text: await runCli(args) }],
        };
      },
    });

    api.registerTool({
      name: "agent_watch_topic",
      description: "Searches Agent Watch items by normalized topic/tag, for example mcp, opencode, open-source-models, coding-agents, or local-inference.",
      parameters: {
        type: "object",
        properties: {
          topic: {
            type: "string",
            description: "Topic/tag to search. It can be passed with or without #.",
          },
          limit: {
            type: "number",
            description: "Maximum number of results. Default 10.",
          },
        },
        required: ["topic"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { topic, limit }: { topic: string; limit?: number }) {
        console.log("[school-guardian-tools] execute agent_watch_topic", topic);
        const args = ["agent-watch-topic", topic];
        if (limit) args.push("--limit", String(limit));
        return {
          content: [{ type: "text", text: await runCli(args) }],
        };
      },
    });

    api.registerTool({
      name: "agent_watch_item_detail",
      description: "Gets the full detail for an Agent Watch item using the source:external_id id returned by searches.",
      parameters: {
        type: "object",
        properties: {
          item_id: {
            type: "string",
            description: "ID in source:external_id format, for example x:123 or rss:https://example.com/post.",
          },
        },
        required: ["item_id"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { item_id }: { item_id: string }) {
        console.log("[school-guardian-tools] execute agent_watch_item_detail", item_id);
        return {
          content: [{ type: "text", text: await runCli(["agent-watch-item", item_id]) }],
        };
      },
    });

    api.registerTool({
      name: "school_guardian_list_pending",
      description: "Lista tareas pendientes reales desde el store interno sincronizado con Classroom.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute school_guardian_list_pending");
        return {
          content: [{ type: "text", text: await runCli(["pending"]) }],
        };
      },
    });

    api.registerTool({
      name: "school_guardian_list_subjects",
      description: "Lista materias con tareas pendientes reales desde el store interno.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute school_guardian_list_subjects");
        return {
          content: [{ type: "text", text: await runCli(["list-subjects"]) }],
        };
      },
    });

    api.registerCommand({
      id: "school_guardian_subjects_command",
      name: "materias",
      description: "Lista materias pendientes desde el store interno.",
      handler: async () => {
        console.log("[school-guardian-tools] execute command /materias");
        return { text: await runCli(["list-subjects"]) };
      },
    });

    api.registerTool({
      name: "school_guardian_list_subjects_cli",
      description: "Lista materias pendientes ejecutando directamente la CLI local de school-guardian.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute school_guardian_list_subjects_cli");
        return {
          content: [
            {
              type: "text",
              text: await runCli(["list-subjects"]),
            },
          ],
        };
      },
    });

    api.registerTool({
      name: "school_guardian_task_detail",
      description: "Obtiene el detalle completo de una tarea incluyendo el texto extraído de documentos adjuntos (Google Docs, Word, PDF). Usar el external_id real de la tarea, por ejemplo el valor mostrado como id:796654380111. No usar el número de orden visual de una lista.",
      parameters: {
        type: "object",
        properties: {
          task_id: {
            type: "string",
            description: "El external_id real de la tarea, obtenido de school_guardian_list_pending como id:..., no el número ordinal de la lista.",
          },
        },
        required: ["task_id"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { task_id }: { task_id: string }) {
        console.log("[school-guardian-tools] execute school_guardian_task_detail", task_id);
        return { content: [{ type: "text", text: await runCli(["task-detail", task_id]) }] };
      },
    });

    api.registerTool({
      name: "school_guardian_export_solution",
      description: "Genera un PDF con la solución de una tarea y lo envía por Telegram. Usar cuando el usuario pide exportar o bajar la solución de una tarea.",
      parameters: {
        type: "object",
        properties: {
          task_id: {
            type: "string",
            description: "El external_id de la tarea (puede ser vacío si no aplica).",
          },
          title: {
            type: "string",
            description: "Título del documento PDF, por ejemplo el nombre de la tarea.",
          },
          solution: {
            type: "string",
            description: "El texto completo de la solución en markdown. Puede incluir encabezados (#, ##), listas (- item) y texto en negrita (**texto**).",
          },
          chat_id: {
            type: "string",
            description: "El Telegram chat_id del usuario que hizo el pedido, para enviarle el PDF directamente.",
          },
        },
        required: ["title", "solution"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { task_id, title, solution, chat_id }: { task_id?: string; title: string; solution: string; chat_id?: string }) {
        const resolvedChatId = (chat_id && chat_id !== "undefined") ? chat_id : lastKnownChatId;
        console.log("[school-guardian-tools] execute school_guardian_export_solution", title, "chat_id=", resolvedChatId);
        const tempDir = await mkdtemp(join(tmpdir(), "school-guardian-"));
        const solutionFile = join(tempDir, "solution.md");
        try {
          await writeFile(solutionFile, solution, "utf8");
          const args = ["export-solution", "--title", title, "--solution-file", solutionFile];
          if (task_id) args.push("--task-id", task_id);
          if (resolvedChatId) args.push("--chat-id", resolvedChatId);
          return {
            content: [{ type: "text", text: await runCli(args) }],
          };
        } finally {
          await rm(tempDir, { recursive: true, force: true });
        }
      },
    });

    api.registerTool({
      name: "school_guardian_analyze_task_images",
      description: "Usa un modelo de visión para analizar las imágenes del documento adjunto de una tarea y devuelve una descripción detallada del contenido. Usar cuando school_guardian_task_detail devuelve extracted_text null para un material drive_file y se necesita entender el contenido.",
      parameters: {
        type: "object",
        properties: {
          task_id: {
            type: "string",
            description: "El external_id de la tarea.",
          },
        },
        required: ["task_id"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { task_id }: { task_id: string }) {
        console.log("[school-guardian-tools] execute school_guardian_analyze_task_images", task_id);
        return {
            content: [{
            type: "text",
            text: await runCli(["analyze-task-images", task_id]),
          }],
        };
      },
    });

    api.registerTool({
      name: "school_guardian_send_task_images",
      description: "Extrae imágenes del documento adjunto de una tarea (DOCX con imágenes) y las envía por Telegram. Usar cuando school_guardian_task_detail devuelve extracted_text null para un material de tipo drive_file.",
      parameters: {
        type: "object",
        properties: {
          task_id: {
            type: "string",
            description: "El external_id de la tarea.",
          },
          chat_id: {
            type: "string",
            description: "El Telegram chat_id del usuario.",
          },
        },
        required: ["task_id"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { task_id, chat_id }: { task_id: string; chat_id?: string }) {
        const resolvedChatId = (chat_id && chat_id !== "undefined") ? chat_id : lastKnownChatId;
        console.log("[school-guardian-tools] execute school_guardian_send_task_images", task_id, "chat_id=", resolvedChatId);
        const args = ["send-task-images", task_id];
        if (resolvedChatId) args.push("--chat-id", resolvedChatId);
        return {
          content: [{
            type: "text",
            text: await runCli(args),
          }],
        };
      },
    });

    api.registerTool({
      name: "school_guardian_web_search",
      description: "Busca en internet usando Brave Search. Usar para explicar conceptos escolares, encontrar ejemplos o recursos educativos cuando la información no está en las tareas.",
      parameters: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "La consulta de búsqueda en español, orientada a nivel secundario.",
          },
        },
        required: ["query"],
        additionalProperties: false,
      },
      async execute(_toolCallId: string, { query }: { query: string }) {
        console.log("[school-guardian-tools] execute school_guardian_web_search", query);
        const apiKey = process.env.BRAVE_SEARCH_API_KEY;
        if (!apiKey) {
          return { content: [{ type: "text", text: "Error: BRAVE_SEARCH_API_KEY no configurada." }] };
        }
        const url = `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=5&search_lang=es`;
        const response = await fetch(url, {
          headers: {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": apiKey,
          },
        });
        if (!response.ok) {
          const text = await response.text();
          throw new Error(`Brave Search error ${response.status}: ${text}`);
        }
        const data: any = await response.json();
        const results = (data.web?.results ?? []).slice(0, 5);
        if (!results.length) {
          return { content: [{ type: "text", text: "No se encontraron resultados." }] };
        }
        const text = results
          .map((r: any, i: number) => `${i + 1}. **${r.title}**\n${r.description ?? ""}\n${r.url}`)
          .join("\n\n");
        return { content: [{ type: "text", text }] };
      },
    });

    api.registerTool({
      name: "school_guardian_daily_focus",
      description: "Devuelve el foco diario real basado en urgencia y vencimientos.",
      parameters: emptyParams,
      async execute() {
        console.log("[school-guardian-tools] execute school_guardian_daily_focus");
        return {
          content: [{ type: "text", text: await runCli(["daily-focus"]) }],
        };
      },
    });
  },
});
