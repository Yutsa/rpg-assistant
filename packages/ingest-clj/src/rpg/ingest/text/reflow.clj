(ns rpg.ingest.text.reflow
  "Reflow PDF line breaks and hyphenation for readable chunk text."
  (:require [clojure.string :as str]))

(def ^:private special-space-re #"[\u00a0\u202f]")
(def ^:private trailing-hyphen-re #"[-\u00ad\u2010\u2011\u2012\u2013\u2014\u2015\u2212]+$")
(def ^:private multi-space-re #" {2,}")

(defn- reflow-paragraph [paragraph]
  (let [lines (vec (remove str/blank? (map str/trim (str/split-lines paragraph))))]
    (when (seq lines)
      (loop [result (first lines) remaining (rest lines)]
        (if (empty? remaining)
          (-> result (str/replace multi-space-re " ") str/trim)
          (let [line (first remaining)]
            (recur (if (re-find trailing-hyphen-re result)
                     (str (str/replace result trailing-hyphen-re "") line)
                     (str result " " line))
                   (rest remaining))))))))

(defn reflow-chunk-text
  "Normalize special spaces, join wrapped lines, handle end-of-line hyphenation."
  [text]
  (let [normalized (str/replace text special-space-re " ")
        paragraphs (str/split normalized #"\n\s*\n")]
    (->> paragraphs
         (map reflow-paragraph)
         (remove str/blank?)
         (str/join "\n\n"))))
