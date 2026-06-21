(ns rpg.ingest.extract.layout
  (:require [clojure.string :as str]
            [rpg.ingest.extract.typography :as typography]))

(def default-line-tolerance 2.0)
(def default-block-gap-factor 1.5)

(defn- non-empty-line? [line-positions]
  (not (str/blank? (typography/line-text line-positions))))

(defn- keep-lines [line-groups]
  (filterv non-empty-line? line-groups))

(defn- start-block [line-groups]
  (when (seq line-groups)
    [(first line-groups)]))

(defn- append-line [current-block line-positions]
  (conj current-block line-positions))

(defn- finish-block [blocks current-block]
  (if (seq current-block)
    (conj blocks current-block)
    blocks))

(defn group-lines-into-blocks [line-groups gap-factor]
  (loop [remaining line-groups
         current-block []
         blocks []]
    (if (empty? remaining)
      (finish-block blocks current-block)
      (let [line (first remaining)
            rest-lines (rest remaining)]
        (if (empty? current-block)
          (recur rest-lines (start-block remaining) blocks)
          (if (typography/same-block? (last current-block) line gap-factor)
            (recur rest-lines (append-line current-block line) blocks)
            (recur rest-lines (start-block remaining)
                   (finish-block blocks current-block))))))))

(defn block-text [block-lines]
  (->> block-lines
       (map typography/line-text)
       (str/join "\n")
       str/trim))

(defn block-bbox [block-lines]
  (let [boxes (map typography/line-bbox block-lines)]
    {:x0 (apply min (map :x0 boxes))
     :y0 (apply min (map :y0 boxes))
     :x1 (apply max (map :x1 boxes))
     :y1 (apply max (map :y1 boxes))}))

(defn block-metadata [block-lines]
  (let [line-count (count block-lines)
        metadata (map typography/line-metadata block-lines)
        sizes (keep :max-font-size metadata)]
    {:source "pdfbox"
     :line-count line-count
     :max-font-size (when (seq sizes) (apply max sizes))
     :avg-font-size (when (seq sizes)
                      (/ (reduce + sizes) (count sizes)))
     :bold? (boolean (some :bold? metadata))}))

(defn block-map [page-number block-index block-lines]
  {:block-index block-index
   :text (block-text block-lines)
   :bbox (block-bbox block-lines)
   :metadata (block-metadata block-lines)})

(defn page-blocks [page-number text-positions]
  (let [lines (->> text-positions
                   (#(typography/group-positions-into-lines % default-line-tolerance))
                   keep-lines)
        block-groups (group-lines-into-blocks lines default-block-gap-factor)]
    (->> block-groups
         (map-indexed (fn [block-index block-lines]
                        (block-map page-number block-index block-lines)))
         (filterv #(not (str/blank? (:text %))))
         vec)))

(defn page-text [blocks]
  (->> blocks (map :text) (str/join "\n\n")))

(defn page-map [page-number width height text-positions]
  (let [blocks (page-blocks page-number text-positions)]
    {:page-number page-number
     :width width
     :height height
     :text (page-text blocks)
     :blocks blocks}))
