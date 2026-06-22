(ns rpg.ingest.extract.raw
  "Minimal PDFBox extraction: one line per block, no column split or merging."
  (:require [rpg.ingest.extract.lines :as lines]
            [rpg.ingest.extract.typography :as typography]))

(defn- collect-lines-raw [text-positions]
  (->> (typography/group-positions-into-lines text-positions lines/default-line-tolerance)
       (map lines/build-line)
       (remove nil?)
       lines/sort-lines-top-down))

(defn- line-as-block [block-index line-record]
  {:block-index block-index
   :text (:text line-record)
   :bbox (:bbox line-record)
   :metadata (assoc (:metadata line-record)
                    :source "pdfbox_raw"
                    :extraction "line")})

(defn page-raw-blocks [page-number width height text-positions]
  (let [blocks (map-indexed line-as-block (collect-lines-raw text-positions))]
    {:page-number page-number
     :width width
     :height height
     :blocks (vec blocks)}))
