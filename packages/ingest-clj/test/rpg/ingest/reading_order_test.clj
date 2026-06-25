(ns rpg.ingest.reading-order-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.reading-order :as ro])
  (:import [java.io File]))

(defn- block
  [idx text x0 y0 x1 y1]
  {:block-index idx
   :text text
   :bbox {:x0 x0 :y0 y0 :x1 x1 :y1 y1}
   :metadata {}})

(deftest column-side-classifies-left-and-right
  (let [page-width 510.0
        left (block 0 "gauche" 40 100 200 120)
        right (block 1 "droite" 260 100 400 120)]
    (is (= :left (ro/column-side left page-width)))
    (is (= :right (ro/column-side right page-width)))))

(deftest normalize-page-blocks-column-major-not-y-interleaved
  (testing "Colonne gauche entière avant droite, même si droite commence plus haut"
    (let [page-width 510.0
          ;; droite y=50 avant gauche y=100 — ancien tri (y0,x0) entremêlerait
          blocks [(block 0 "R-haut" 260 50 400 70)
                  (block 1 "L-bas" 40 200 200 220)
                  (block 2 "L-haut" 40 100 200 120)
                  (block 3 "R-bas" 260 150 400 170)]
          ordered (ro/normalize-page-blocks blocks page-width)
          texts (mapv :text ordered)
          indices (mapv :block-index ordered)]
      (is (= ["L-haut" "L-bas" "R-haut" "R-bas"] texts))
      (is (= [0 1 2 3] indices))
      (is (ro/column-major-ordered? ordered page-width)))))

(deftest reindex-blocks-starts-at-zero
  (is (= [0 1 2] (mapv :block-index (ro/reindex-blocks [{:block-index 5} {:block-index 9} {}])))))

(deftest momie-page-7-blocks-are-column-major-ordered
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [page (pdf/extract-page (.getAbsolutePath momie) 7)
            blocks (:blocks page)
            width (:width page)]
        (is (ro/column-major-ordered? blocks width)
            "every block list must follow column-major reading order")
        (is (= (range (count blocks)) (mapv :block-index blocks))
            "block-index must be 0..n-1 in reading order")))))

(deftest momie-page-7-left-column-before-right-column
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [page (pdf/extract-page (.getAbsolutePath momie) 7)
            width (:width page)
            sides (mapv #(ro/column-side % width) (:blocks page))
            pivot (count (take-while #(= :left %) sides))]
        (is (pos? pivot) "page 7 must have left-column blocks")
        (is (< pivot (count sides)) "page 7 must have right-column blocks")
        (is (every? #{:left} (take pivot sides))
            "prefix is entirely left column")
        (is (every? #{:right} (drop pivot sides))
            "suffix is entirely right column")))))

(deftest momie-page-7-left-column-y-non-decreasing
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [page (pdf/extract-page (.getAbsolutePath momie) 7)
            width (:width page)
            left-blocks (filter #(= :left (ro/column-side % width)) (:blocks page))
            ys (map #(get-in % [:bbox :y0]) left-blocks)]
        (is (= ys (sort ys))
            "left column blocks read top-to-bottom")))))

(deftest momie-page-7-reading-order-content-sanity
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [page (pdf/extract-page (.getAbsolutePath momie) 7)
            width (:width page)
            blocks (:blocks page)
            left-blocks (filter #(= :left (ro/column-side % width)) blocks)
            right-blocks (filter #(= :right (ro/column-side % width)) blocks)]
        (is (str/includes? (:text (first blocks)) "Dans les vestiges")
            "index 0 is top-left summary (left column)")
        (is (re-find #"L.histoire pour le MJ" (:text (second blocks)))
            "index 1 is MJ heading still in left column")
        (is (str/includes? (:text (first right-blocks)) "Depuis lors")
            "right column starts after entire left column is read")
        (is (some #(str/includes? (:text %) "Taless Rhann") left-blocks)
            "MJ body stays in left column")))))

(deftest normalize-reading-order-preserves-page-count
  (let [pages [{:page-number 1 :width 500.0 :height 700.0 :blocks []}
               {:page-number 2 :width 500.0 :height 700.0 :blocks []}]]
    (is (= 2 (count (ro/normalize-reading-order pages))))))
