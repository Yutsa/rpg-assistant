(ns rpg.ingest.extract.typography
  (:require [clojure.string :as str])
  (:import [org.apache.pdfbox.text TextPosition]))

(defn position-x [text-position]
  (.getXDirAdj ^TextPosition text-position))

(defn position-y [text-position]
  (.getYDirAdj ^TextPosition text-position))

(defn position-width [text-position]
  (.getWidthDirAdj ^TextPosition text-position))

(defn position-height [text-position]
  (.getHeight ^TextPosition text-position))

(defn position-font-size [text-position]
  (.getFontSizeInPt ^TextPosition text-position))

(defn position-text [text-position]
  (.getUnicode ^TextPosition text-position))

(defn position-bold? [text-position]
  (let [font (.getFont ^TextPosition text-position)
        font-name (when font (.getName font))]
    (boolean (and font-name (re-find #"(?i)bold" font-name)))))

(defn position-italic? [text-position]
  (let [font (.getFont ^TextPosition text-position)
        font-name (when font (.getName font))]
    (boolean (and font-name (re-find #"(?i)(italic|oblique)" font-name)))))

(defn line-key [text-position tolerance]
  (Math/round (/ (position-y text-position) tolerance)))

(defn sort-positions [text-positions]
  (sort-by (juxt position-y position-x) text-positions))

(defn group-positions-into-lines [text-positions tolerance]
  (->> (sort-positions text-positions)
       (group-by #(line-key % tolerance))
       (sort-by key)
       (map (fn [[_key positions]] positions))
       vec))
