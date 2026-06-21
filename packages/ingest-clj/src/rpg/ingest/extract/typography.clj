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

(defn line-text [line-positions]
  (->> line-positions
       (map position-text)
       (apply str)
       str/trim))

(defn line-bbox [line-positions]
  (let [left (apply min (map position-x line-positions))
        top (apply min (map position-y line-positions))
        right (apply max (map #(+ (position-x %)
                                  (position-width %)) line-positions))
        bottom (apply max (map #(+ (position-y %)
                                   (position-height %)) line-positions))]
    {:x0 left :y0 top :x1 right :y1 bottom}))

(defn line-font-sizes [line-positions]
  (map position-font-size line-positions))

(defn line-metadata [line-positions]
  (let [sizes (line-font-sizes line-positions)
        average-size (when (seq sizes) (/ (reduce + sizes) (count sizes)))]
    {:source "pdfbox"
     :line-count 1
     :max-font-size (when (seq sizes) (apply max sizes))
     :avg-font-size average-size
     :bold? (boolean (some position-bold? line-positions))}))

(defn line-vertical-gap [previous-line current-line]
  (- (position-y (first current-line))
     (+ (position-y (first previous-line))
        (position-height (first previous-line)))))

(defn same-block? [previous-line current-line gap-factor]
  (let [line-height (max (position-height (first previous-line)) 1.0)
        gap (line-vertical-gap previous-line current-line)]
    (<= gap (* line-height gap-factor))))
