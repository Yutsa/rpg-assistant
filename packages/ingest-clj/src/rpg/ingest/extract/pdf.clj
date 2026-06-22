(ns rpg.ingest.extract.pdf
  (:require [rpg.ingest.extract.layout :as layout]
            [rpg.ingest.extract.raw :as raw]
            [rpg.ingest.schema :as schema])
  (:import [java.io File]
           [org.apache.pdfbox Loader]
           [org.apache.pdfbox.pdmodel PDDocument]
           [org.apache.pdfbox.text PDFTextStripper]
           [org.apache.pdfbox.text TextPosition]))

(defn- collect-page-positions [document page-index]
  (let [positions (atom [])]
    (doto (proxy [PDFTextStripper] []
            (writeString [_string text-positions]
              (swap! positions into text-positions)))
      (.setSortByPosition true)
      (.setStartPage (inc page-index))
      (.setEndPage (inc page-index))
      (.getText document))
    @positions))

(defn- page-dimensions [document page-index]
  (let [page (.getPage document page-index)
        box (.getMediaBox page)]
    {:width (.getWidth box)
     :height (.getHeight box)}))

(defn- page-layout [document page-index]
  (let [page-number (inc page-index)
        dimensions (page-dimensions document page-index)
        positions (collect-page-positions document page-index)]
    (layout/page-map page-number (:width dimensions) (:height dimensions) positions)))

(defn extract-layout [pdf-path]
  (with-open [document (Loader/loadPDF (File. pdf-path))]
    (let [page-count (.getNumberOfPages document)
          pages (mapv #(page-layout document %) (range page-count))]
      (schema/validate schema/LayoutDocument
                       {:source-path pdf-path :pages pages}
                       "layout document"))))

(defn extract-raw-page [pdf-path page-number]
  (with-open [document (Loader/loadPDF (File. pdf-path))]
    (let [page-index (dec page-number)
          page-count (.getNumberOfPages document)]
      (when (or (< page-index 0) (>= page-index page-count))
        (throw (ex-info "Page number out of range"
                        {:page-number page-number :page-count page-count})))
      (let [dimensions (page-dimensions document page-index)
            positions (collect-page-positions document page-index)]
        (raw/page-raw-blocks page-number
                             (:width dimensions)
                             (:height dimensions)
                             positions)))))

(defn extract-layout-page [pdf-path page-number]
  (with-open [document (Loader/loadPDF (File. pdf-path))]
    (let [page-index (dec page-number)
          page-count (.getNumberOfPages document)]
      (when (or (< page-index 0) (>= page-index page-count))
        (throw (ex-info "Page number out of range"
                        {:page-number page-number :page-count page-count})))
      (page-layout document page-index))))

(defn with-document [pdf-path callback]
  (with-open [document (Loader/loadPDF (File. pdf-path))]
    (callback document)))
