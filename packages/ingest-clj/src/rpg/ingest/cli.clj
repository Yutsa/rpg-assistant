(ns rpg.ingest.cli
  (:require [cheshire.core :as json]
            [clojure.string :as str]
            [clojure.tools.cli :as cli]
            [rpg.ingest.import :as import]))

(def cli-options
  [["p" "--pdf PATH" "Path to the PDF file"]
   ["c" "--campaign-id ID" "Campaign identifier"]
   ["t" "--campaign-title TITLE" "Campaign title" :default ""]
   ["g" "--game-system SYSTEM" "Game system label" :default ""]
   [nil "--no-reimport" "Keep existing raw rows for the document"]
   ["h" "--help" "Show usage"]])

(defn- snake-case-key [key-value]
  (-> (name key-value) (str/replace "-" "_")))

(defn- result-json [result]
  (json/generate-string result {:pretty true :key-fn snake-case-key}))

(defn- usage [summary]
  (str/join "\n"
            ["RPG Assistant — raw PDF extraction (Clojure)"
             ""
             "Usage: clojure -M:ingest raw extract [options]"
             ""
             (:summary summary)]))

(defn- parse-arguments [command-args]
  (cli/parse-opts command-args cli-options))

(defn- missing-required? [options]
  (or (nil? (:pdf options)) (nil? (:campaign-id options))))

(defn- exit-code [result]
  (if (= "completed" (:status result)) 0 1))

(defn extract-command [command-args]
  (let [{:keys [options summary errors]} (parse-arguments command-args)]
    (cond
      (seq errors) (do (println errors) 1)
      (:help options) (do (println (usage {:summary summary})) 0)
      (missing-required? options) (do (println "Missing --pdf or --campaign-id") 1)
      :else (let [result (import/run-import
                          (:pdf options)
                          {:campaign-id (:campaign-id options)
                           :campaign-title (:campaign-title options)
                           :game-system (:game-system options)
                           :reimport? (not (:no-reimport options))})]
              (println (result-json result))
              (exit-code result)))))

(defn -main [& args]
  (let [[subcommand action & rest-args] args]
    (if (and (= subcommand "raw") (= action "extract"))
      (System/exit (extract-command rest-args))
      (do
        (println (usage (cli/parse-opts [] cli-options)))
        (System/exit 1)))))
