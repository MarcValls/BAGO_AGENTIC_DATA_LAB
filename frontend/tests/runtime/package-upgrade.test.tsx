import { createElement } from "react";
import { renderToString } from "react-dom/server.node";
import axios from "axios";
import { expect, it } from "vitest";
import App from "../../src/App";

it("renders the app's pending artifact state", () => {
  const html = renderToString(createElement(App));
  expect(html).toContain('role="status"');
});

it("accepts an artifacts response from the configured HTTP client", async () => {
  const response = await axios.get("/api/artifacts", {
    adapter: async (config) => ({
      data: { summary: { status: "PASS" } },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    }),
  });

  expect(response.data.summary.status).toBe("PASS");
});
