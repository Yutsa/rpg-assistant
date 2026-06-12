import { copyFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

mkdirSync("dist/assets", { recursive: true });
copyFileSync("public/index.html", "dist/index.html");
copyFileSync("src/index.css", "dist/assets/index.css");
