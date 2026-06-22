(ns rpg.ingest.cli
  (:require [cheshire.core :as json]
            [clojure.string :as str]
            [clojure.tools.cli :as cli]
            [rpg.ingest.extract.pdf :as pdf]))

(def extract-page-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["n" "--page NUMBER" "1-based page number" :parse-fn #(Integer/parseInt %)]
   ["h" "--help" "Show usage"]])

(def extract-document-options
  [["p" "--pdf PATH" "Path to the PDF file"]
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

(defn -main [& args]
  (let [[subcommand action & rest-args] args]
    (cond
      (and (= subcommand "raw") (= action "extract-page"))
      (System/exit (extract-page-command rest-args))

      (and (= subcommand "raw") (= action "extract-document"))
      (System/exit (extract-document-command rest-args))

      (= subcommand "serve")
      (serve-command)

      :else
      (do
        (println (usage (cli/parse-opts [] extract-page-options)))
        (System/exit 1)))))
