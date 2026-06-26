(ns rpg.ingest.test-fixtures.layout
  (:require [clojure.string :as str]))

(defn make-block
  [page-number block-index text & {:keys [font-size bold italic x0 y0 x1 y1 metadata]
                                   :or {bold false
                                        italic false
                                        x0 0.0
                                        y0 0.0
                                        x1 100.0
                                        y1 nil}}]
  (let [y1' (or y1 (+ y0 20.0))
        line-count (if (str/includes? text "\n")
                     (count (str/split text #"\n"))
                     1)
        base-meta (or metadata {})
        meta (if font-size
               (merge {:max-font-size font-size
                       :avg-font-size font-size
                       :is-bold bold
                       :is-italic italic
                       :line-count line-count}
                      base-meta)
               base-meta)]
    {:page-number page-number
     :block-index block-index
     :text text
     :bbox {:x0 x0 :y0 y0 :x1 x1 :y1 y1'}
     :metadata meta}))

(defn make-page
  [blocks & {:keys [page-number width height]
             :or {width 612.0 height 792.0}}]
  (let [page-num (or page-number (:page-number (first blocks)) 1)]
    {:page-number page-num
     :width width
     :height height
     :text (clojure.string/join "\n\n" (map :text blocks))
     :blocks blocks}))
