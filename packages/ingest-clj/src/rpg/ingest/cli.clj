(ns rpg.ingest.cli
  (:require [cheshire.core :as json]
            [clojure.string :as str]
            [clojure.tools.cli :as cli]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.pipeline :as pipeline]))

(def extract-page-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["n" "--page NUMBER" "1-based page number" :parse-fn #(Integer/parseInt %)]
   ["h" "--help" "Show usage"]])

(def extract-document-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["h" "--help" "Show usage"]])

(def import-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["c" "--campaign-id ID" "Campaign id"]
   ["t" "--campaign-title TITLE" "Campaign title (optional)"]
   ["g" "--game-system SYSTEM" "Game system (optional)"]
   ["d" "--db PATH" "SQLite database path or sqlite: URL (optional)"]
   [nil "--no-reimport" "Keep existing raw data for this document"]
   ["h" "--help" "Show usage"]])

(defn- snake-case-key [key-value]
  (-> (name key-value) (str/replace "-" "_")))

(defn- result-json [result]
  (json/generate-string result {:key-fn snake-case-key}))

(defn- usage [summary]
  (str/join "\n"
            ["RPG Assistant — PDFBox ingestion (Clojure)"
             ""
             "Usage:"
             "  clojure -M:ingest import --pdf PATH --campaign-id ID"
             "  clojure -M:ingest raw extract-page --pdf PATH --page N"
             "  clojure -M:ingest raw extract-document --pdf PATH"
             "  clojure -M:ingest serve"
             ""
             summary]))

(defn- handle-serve-request [line]
  (try
    (let [request (json/parse-string line true)
          pdf-path (:pdf request)
          page-number (:page request)]
      (cond
        (or (nil? pdf-path) (nil? page-number))
        (result-json {:error "Missing pdf or page"})
        :else (result-json (pdf/extract-page pdf-path page-number))))
    (catch Exception e
      (result-json {:error (.getMessage e)}))))

(defn serve-command []
  (println (result-json {:ready true}))
  (flush)
  (loop []
    (when-let [line (read-line)]
      (when-not (str/blank? line)
        (println (handle-serve-request line))
        (flush))
      (recur))))

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

(defn extract-document-command [command-args]
  (let [{:keys [options summary errors]} (cli/parse-opts command-args extract-document-options)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (usage summary)) 0)
      (nil? (:pdf options)) (do (println "Missing --pdf") 1)

      :else (try
              (println (result-json (pdf/extract-document (:pdf options))))
              0
              (catch Exception e
                (println (result-json {:error (.getMessage e)}))
                1)))))

(defn import-command [command-args]
  (let [{:keys [options summary errors]} (cli/parse-opts command-args import-options)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (usage summary)) 0)
      (or (nil? (:pdf options)) (nil? (:campaign-id options)))
      (do (println "Missing --pdf or --campaign-id") 1)

      :else (try
              (println
               (result-json
                (pipeline/import-pdf!
                 {:pdf-path (:pdf options)
                  :campaign-id (:campaign-id options)
                  :campaign-title (:campaign-title options)
                  :game-system (:game-system options)
                  :db-spec (:db options)
                  :reimport (not (:no-reimport options))})))
              0
              (catch Exception e
                (println (result-json {:error (.getMessage e)}))
                1)))))

(defn -main [& args]
  (let [[subcommand & rest-args] args]
    (cond
      (= subcommand "import")
      (System/exit (import-command rest-args))

      (and (= subcommand "raw") (= (first rest-args) "extract-page"))
      (System/exit (extract-page-command (rest rest-args)))

      (and (= subcommand "raw") (= (first rest-args) "extract-document"))
      (System/exit (extract-document-command (rest rest-args)))

      (= subcommand "serve")
      (serve-command)

      :else
      (do
        (println (usage (cli/parse-opts [] import-options)))
        (System/exit 1)))))
