(ns rpg.ingest.extract.layout
  (:require [clojure.string :as str]
            [rpg.ingest.extract.blocks :as blocks]
            [rpg.ingest.extract.lines :as lines]))

(defn page-text [block-records]
  (->> block-records (map :text) (str/join "\n\n")))

(defn page-map [page-number width height text-positions]
  (let [line-records (lines/collect-lines text-positions width)
        block-records (->> (blocks/blocks-from-page-lines line-records width)
                           (filterv #(not (str/blank? (:text %))))
                           vec)]
    {:page-number page-number
     :width width
     :height height
     :text (page-text block-records)
     :blocks block-records}))
