(ns rpg.ingest.stat-blocks.text-utils
  (:require [clojure.string :as str]))

(def ^:private pua-re #"[\uE000-\uF8FF]")
(def ^:private icon-line-re #"^W\s*$")
(def ^:private control-char-re #"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
(def ^:private drm-name-line-re #"^W\s+(.+)$")

(defn normalize-spaces
  [text]
  (-> text
      (str/replace "\u202f" " ")
      (str/replace "\u00a0" " ")))

(defn- clean-line [line]
  (let [stripped (-> line
                     (str/replace control-char-re "")
                     (str/replace pua-re "")
                     str/trim)]
    (cond
      (empty? stripped) ""
      (re-matches drm-name-line-re stripped) (str/trim (second (re-matches drm-name-line-re stripped)))
      :else stripped)))

(defn strip-layout-glyphs
  "Remove CoF layout icon glyphs (PUA chars and lone W lines)."
  [text]
  (->> (str/split-lines (normalize-spaces text))
       (keep (fn [line]
               (let [stripped (clean-line line)]
                 (when (and (seq stripped)
                            (not (re-matches icon-line-re stripped)))
                   stripped))))
       (str/join "\n")
       str/trim))

(defn has-icon-glyphs?
  [text]
  (or (boolean (re-find pua-re text))
      (some #(re-matches icon-line-re (str/trim %))
            (filter seq (str/split-lines text)))))

(defn- leaked-ability-title-line? [line]
  (let [t (str/trim line)]
    (and (seq t)
         (<= (count t) 20)
         (not (re-find #"[.!?]$" t))
         (not (re-find #"(?i)\b(de|la|le|un|une|du|des|les|et|ou|si|au|en|par|pour|avec|sur|est|tous|que|qui)\b" t))
         (or (has-icon-glyphs? t)
             (and (not (re-find #"\s" t))
                  (>= (count (re-seq #"[A-ZÀ-ÿ]" t)) 2))))))

(defn- icon-only-ability-title-line? [line]
  (or (leaked-ability-title-line? line)
      (and (has-icon-glyphs? line)
           (let [stripped (strip-layout-glyphs line)]
             (and (seq stripped)
                  (<= (count stripped) 20))))))

(defn clean-ability-text
  "Drop icon-glyph ability title lines leaked into body text."
  [text]
  (->> (str/split-lines text)
       (remove icon-only-ability-title-line?)
       (str/join "\n")
       str/trim))

(defn normalize-attack-separators
  "Normalize COF2 attack damage separators corrupted by PDF font encoding."
  [text]
  (-> text
      (str/replace #"Åàé" "· DM")
      (str/replace #"[\u00b7]" "·")))
