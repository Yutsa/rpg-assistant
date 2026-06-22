(ns rpg.ingest.cli
  (:require [cheshire.core :as json]
            [clojure.string :as str]
            [clojure.tools.cli :as cli]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.import :as import]))

(def extract-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["c" "--campaign-id ID" "Campaign identifier"]
   ["t" "--campaign-title TITLE" "Campaign title" :default ""]
   ["g" "--game-system SYSTEM" "Game system label" :default ""]
   [nil "--no-reimport" "Keep existing raw rows for the document"]
   ["h" "--help" "Show usage"]])

(def extract-page-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["n" "--page NUMBER" "1-based page number" :parse-fn #(Integer/parseInt %)]
   ["h" "--help" "Show usage"]])

(defn- snake-case-key [key-value]
  (-> (name key-value) (str/replace "-" "_")))

(defn- result-json [result]
  (json/generate-string result {:key-fn snake-case-key}))

(defn- extract-usage [summary]
  (str/join "\n"
            ["RPG Assistant — raw PDF extraction (Clojure)"
             ""
             "Usage:"
             "  clojure -M:ingest raw extract [options]"
             "  clojure -M:ingest raw extract-page --pdf PATH --page N"
             "  clojure -M:ingest raw extract-layout-page --pdf PATH --page N"
             ""
             (:summary summary)]))

(defn- exit-code [result]
  (if (= "completed" (:status result)) 0 1))

(defn extract-command [command-args]
  (let [{:keys [options summary errors]} (cli/parse-opts command-args extract-options)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (extract-usage {:summary summary})) 0)
      (or (nil? (:pdf options)) (nil? (:campaign-id options)))
      (do (println "Missing --pdf or --campaign-id") 1)

      :else (let [result (import/run-import
                          (:pdf options)
                          {:campaign-id (:campaign-id options)
                           :campaign-title (:campaign-title options)
                           :game-system (:game-system options)
                           :reimport? (not (:no-reimport options))})]
              (println (json/generate-string result {:pretty true :key-fn snake-case-key}))
              (exit-code result)))))

(defn extract-page-command [command-args]
  (let [{:keys [options summary errors]} (cli/parse-opts command-args extract-page-options)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (extract-usage {:summary summary})) 0)
      (or (nil? (:pdf options)) (nil? (:page options)))
      (do (println "Missing --pdf or --page") 1)

      :else (try
              (println (result-json (pdf/extract-raw-page (:pdf options) (:page options))))
              0
              (catch Exception e
                (println (result-json {:error (.getMessage e)}))
                1)))))

(defn extract-layout-page-command [command-args]
  (let [{:keys [options summary errors]} (cli/parse-opts command-args extract-page-options)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (extract-usage {:summary summary})) 0)
      (or (nil? (:pdf options)) (nil? (:page options)))
      (do (println "Missing --pdf or --page") 1)

      :else (try
              (println (result-json (pdf/extract-layout-page (:pdf options) (:page options))))
              0
              (catch Exception e
                (println (result-json {:error (.getMessage e)}))
                1)))))

(defn -main [& args]
  (let [[subcommand action & rest-args] args]
    (cond
      (and (= subcommand "raw") (= action "extract"))
      (System/exit (extract-command rest-args))

      (and (= subcommand "raw") (= action "extract-page"))
      (System/exit (extract-page-command rest-args))

      (and (= subcommand "raw") (= action "extract-layout-page"))
      (System/exit (extract-layout-page-command rest-args))

      :else
      (do
        (println (extract-usage (cli/parse-opts [] extract-options)))
        (System/exit 1)))))
