(ns rpg.ingest.extract.blocks
  (:require [clojure.string :as str]
            [rpg.ingest.extract.columns :as columns]
            [rpg.ingest.extract.lines :as lines]))

(defn- start-block [line-record]
  [line-record])

(defn- append-line [block-lines line-record]
  (conj block-lines line-record))

(defn- finish-block [blocks block-lines]
  (if (seq block-lines)
    (conj blocks block-lines)
    blocks))

(defn group-lines-into-block-lines [line-records]
  (loop [remaining line-records
         current-block []
         blocks []]
    (if (empty? remaining)
      (finish-block blocks current-block)
      (let [line (first remaining)
            rest-lines (rest remaining)]
        (if (empty? current-block)
          (recur rest-lines (start-block line) blocks)
          (if (lines/can-merge-lines? (last current-block) line)
            (recur rest-lines (append-line current-block line) blocks)
            (recur rest-lines (start-block line)
                   (finish-block blocks current-block))))))))

(defn block-text [block-lines]
  (->> block-lines (map :text) (str/join "\n") str/trim))

(defn block-bbox [block-lines]
  (let [boxes (map :bbox block-lines)]
    {:x0 (apply min (map :x0 boxes))
     :y0 (apply min (map :y0 boxes))
     :x1 (apply max (map :x1 boxes))
     :y1 (apply max (map :y1 boxes))}))

(defn block-metadata [block-lines]
  (let [line-count (count block-lines)
        metadata (map :metadata block-lines)
        sizes (keep :max-font-size metadata)]
    {:source "pdfbox"
     :line-count line-count
     :max-font-size (when (seq sizes) (apply max sizes))
     :avg-font-size (when (seq sizes)
                      (/ (reduce + sizes) (count sizes)))
     :bold? (boolean (some :bold? metadata))
     :italic? (boolean (some :italic? metadata))}))

(defn block-map [block-index block-lines]
  {:block-index block-index
   :text (block-text block-lines)
   :bbox (block-bbox block-lines)
   :metadata (block-metadata block-lines)})

(defn blocks-from-line-records [line-records]
  (->> (group-lines-into-block-lines line-records)
       (map-indexed (fn [block-index block-lines]
                      (block-map block-index block-lines)))
       (filterv #(not (str/blank? (:text %))))
       vec))

(defn blocks-from-page-lines [line-records page-width]
  (let [{:keys [left right]} (columns/split-lines-by-column line-records page-width)
        ordered (vec (concat (blocks-from-line-records left)
                             (blocks-from-line-records right)))
        sorted (columns/column-major-block-order ordered page-width)
        tagged (columns/assign-block-columns sorted page-width)]
    (mapv (fn [block-index block]
            (assoc block :block-index block-index))
          (range)
          tagged)))
