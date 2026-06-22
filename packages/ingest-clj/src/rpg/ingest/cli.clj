(ns rpg.ingest.cli
  (:require [cheshire.core :as json]
            [clojure.string :as str]
            [clojure.tools.cli :as cli]
            [rpg.ingest.extract.pdf :as pdf]))

(def extract-page-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["n" "--page NUMBER" "1-based page number" :parse-fn #(Integer/parseInt %)]
   ["h" "--help" "Show usage"]])

(defn- snake-case-key [key-value]
  (-> (name key-value) (str/replace "-" "_")))

(defn- result-json [result]
  (json/generate-string result {:key-fn snake-case-key}))

(defn- usage [summary]
  (str/join "\n"
            ["RPG Assistant — PDFBox raw page extraction (Clojure)"
             ""
             "Usage:"
             "  clojure -M:ingest raw extract-page --pdf PATH --page N"
             ""
             summary]))

(defn extract-page-command [command-args]
  (let [{:keys [options summary errors]} (cli/parse-opts command-args extract-page-options)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (usage summary)) 0)
      (or (nil? (:pdf options)) (nil? (:page options)))
      (do (println "Missing --pdf or --page") 1)

      :else (try
              (println (result-json (pdf/extract-page (:pdf options) (:page options))))
              0
              (catch Exception e
                (println (result-json {:error (.getMessage e)}))
                1)))))

(defn -main [& args]
  (let [[subcommand action & rest-args] args]
    (cond
      (and (= subcommand "raw") (= action "extract-page"))
      (System/exit (extract-page-command rest-args))

      :else
      (do
        (println (usage (cli/parse-opts [] extract-page-options)))
        (System/exit 1)))))
