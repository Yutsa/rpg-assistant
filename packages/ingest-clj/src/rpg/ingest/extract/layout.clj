(ns rpg.ingest.extract.layout
  (:require [clojure.string :as str]
            [rpg.ingest.extract.blocks :as blocks]
            [rpg.ingest.extract.columns :as columns]
            [rpg.ingest.extract.lines :as lines]))

(defn page-text [block-records]
  (->> block-records (map :text) (str/join "\n\n")))

(defn page-map [page-number width height text-positions]
  (let [gutter (columns/page-gutter-from-positions text-positions width lines/default-line-tolerance)
        line-records (lines/collect-lines text-positions width gutter)
        block-records (->> (blocks/blocks-from-page-lines line-records width gutter)
                           (filterv #(not (str/blank? (:text %))))
                           vec)]
    {:page-number page-number
     :width width
     :height height
     :text (page-text block-records)
     :blocks block-records}))
