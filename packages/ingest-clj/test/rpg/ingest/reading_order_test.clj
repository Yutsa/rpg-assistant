(ns rpg.ingest.reading-order-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.reading-order :as ro]
            [rpg.ingest.test-fixtures.pdf :as sample-pdf])
  (:import [java.io File]))

(defn- block
  [idx text x0 y0 x1 y1]
  {:block-index idx
   :text text
   :bbox {:x0 x0 :y0 y0 :x1 x1 :y1 y1}
   :metadata {}})

(deftest spatial-sort-key-orders-by-y-then-x0
  (is (= [[50.0 260] [100.0 40] [150.0 260] [200.0 40]]
         (mapv ro/spatial-sort-key
               (ro/sort-blocks-spatial
                [(block 0 "R-haut" 260 50 400 70)
                 (block 1 "L-bas" 40 200 200 220)
                 (block 2 "L-haut" 40 100 200 120)
                 (block 3 "R-bas" 260 150 400 170)])))))

(deftest normalize-page-blocks-spatial-y-interleaved
  (testing "Tri par bande y puis x0 (comme PyMuPDF / Python)"
    (let [blocks [(block 0 "R-haut" 260 50 400 70)
                  (block 1 "L-bas" 40 200 200 220)
                  (block 2 "L-haut" 40 100 200 120)
                  (block 3 "R-bas" 260 150 400 170)]
          ordered (ro/normalize-page-blocks blocks)]
      (is (= ["R-haut" "L-haut" "R-bas" "L-bas"] (mapv :text ordered)))
      (is (= [0 1 2 3] (mapv :block-index ordered)))
      (is (ro/spatial-ordered? ordered)))))

(deftest reindex-blocks-starts-at-zero
  (is (= [0 1 2] (mapv :block-index (ro/reindex-blocks [{:block-index 5} {:block-index 9} {}])))))

(deftest single-column-pdf-spatial-order-is-top-to-bottom
  (let [temp-file (doto (File/createTempFile "rpg-ingest-1col-" ".pdf")
                    (.deleteOnExit))
        pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
        page (pdf/extract-page pdf-path 1)
        ys (map #(get-in % [:bbox :y0]) (:blocks page))]
    (is (ro/spatial-ordered? (:blocks page)))
    (is (= ys (sort ys)))))

(deftest momie-page-7-blocks-are-spatially-ordered
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [page (pdf/extract-page (.getAbsolutePath momie) 7)
            blocks (:blocks page)]
        (is (ro/spatial-ordered? blocks))
        (is (= (range (count blocks)) (mapv :block-index blocks)))))))

(deftest momie-page-7-blocks-sorted-by-y-then-x
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [blocks (:blocks (pdf/extract-page (.getAbsolutePath momie) 7))
            keys (mapv ro/spatial-sort-key blocks)]
        (is (ro/spatial-ordered? blocks))
        (is (= keys (sort keys)))))))

(deftest momie-page-7-left-cluster-y-non-decreasing
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [blocks (:blocks (pdf/extract-page (.getAbsolutePath momie) 7))
            left-blocks (filter #(< (get-in % [:bbox :x0]) 120.0) blocks)
            ys (map #(get-in % [:bbox :y0]) left-blocks)]
        (is (= ys (sort ys)))))))

(deftest momie-page-7-reading-order-content-sanity
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [blocks (:blocks (pdf/extract-page (.getAbsolutePath momie) 7))
            left-blocks (filter #(< (get-in % [:bbox :x0]) 120.0) blocks)
            right-blocks (filter #(> (get-in % [:bbox :x0]) 200.0) blocks)]
        (is (re-find #"Dans les vestiges" (:text (first blocks))))
        (is (some #(re-find #"L.histoire pour le MJ" (:text %)) blocks))
        (is (re-find #"Depuis lors" (:text (first right-blocks))))
        (is (some #(re-find #"Taless Rhann" (:text %)) left-blocks))))))

(deftest is-in-column-band-detects-same-x-band
  (let [left (block 0 "a" 40 100 200 120)
        right (block 1 "b" 260 100 400 120)]
    (is (ro/is-in-column-band? left left))
    (is (not (ro/is-in-column-band? left right)))))

(deftest normalize-reading-order-preserves-page-count
  (let [pages [{:page-number 1 :width 500.0 :height 700.0 :blocks []}
               {:page-number 2 :width 500.0 :height 700.0 :blocks []}]]
    (is (= 2 (count (ro/normalize-reading-order pages))))))
