(ns rpg.ingest.coverage
  "Heuristic text coverage for rejecting scanned/image-only PDFs.")

(def default-coverage-threshold 0.3)

(defn page-text-coverage-ratio
  "Estimate how much of a page area is covered by extracted text."
  [text page-width page-height]
  (if (or (<= page-width 0) (<= page-height 0))
    0.0
    (let [stripped (clojure.string/trim (or text ""))]
      (if (empty? stripped)
        0.0
        (let [char-count (count stripped)
              page-area (* page-width page-height)
              estimated-text-area (* char-count 50.0)]
          (min 1.0 (/ estimated-text-area page-area)))))))

(defn document-coverage-ratio
  [page-ratios]
  (if (empty? page-ratios)
    0.0
    (/ (reduce + page-ratios) (count page-ratios))))

(defn scanned-or-unusable?
  ([page-ratios] (scanned-or-unusable? page-ratios default-coverage-threshold))
  ([page-ratios threshold]
   (< (document-coverage-ratio page-ratios) threshold)))
