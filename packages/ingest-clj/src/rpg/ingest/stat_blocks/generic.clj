(ns rpg.ingest.stat-blocks.generic
  (:require [clojure.string :as str]
            [rpg.ingest.stat-blocks.core :as core]))

(def ^:private table-re #"(\|.+\|)|(\bAC\b|\bHP\b|\bSpeed\b)")
(def ^:private stat-block-re #"(?i)\b(armor class|hit points|challenge rating)\b")

(defmethod core/matches-document? :generic [_ _pages] false)

(defmethod core/detect-spans :generic [_ pages]
  {:pages pages :spans []})

(defmethod core/parse-span :generic [_ span]
  {:name ""
   :raw-text (->> (:blocks span) (map :text) (str/join "\n\n"))
   :game-system "generic"})

(defmethod core/false-heading? :generic [_ block _page-blocks _idx _page]
  (#{"header" "stats" "icon"} (get-in block [:metadata :stat-block-role])))

(defmethod core/normalize-block-text :generic [_ text] text)

(defmethod core/chunk-type-hint :generic [_ text blocks]
  (cond
    (re-find stat-block-re text) "stat_block"
    (re-find table-re text) "stat_block"
    (and (<= (count blocks) 3)
         (< (apply max 0 (map #(count (:text %)) blocks)) 80)) "table"
    :else nil))
