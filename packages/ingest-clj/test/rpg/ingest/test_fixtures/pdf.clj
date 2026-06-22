(ns rpg.ingest.test-fixtures.pdf
  (:import [java.io File]
           [org.apache.pdfbox.pdmodel PDDocument PDPage]
           [org.apache.pdfbox.pdmodel.common PDRectangle]
           [org.apache.pdfbox.pdmodel.font PDType1Font]
           [org.apache.pdfbox.pdmodel.font Standard14Fonts$FontName]
           [org.apache.pdfbox.pdmodel PDPageContentStream]))

(defn- write-line [content-stream font-size text x-offset y-offset]
  (.beginText content-stream)
  (.setFont content-stream (PDType1Font. Standard14Fonts$FontName/HELVETICA) font-size)
  (.newLineAtOffset content-stream x-offset y-offset)
  (.showText content-stream text)
  (.endText content-stream))

(defn create-sample-pdf [file-path & {:keys [lines]
                                      :or {lines ["Premiere ligne de test." "Deuxieme ligne de test."]}}]
  (let [file (File. file-path)]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (doseq [[index line-text] (map-indexed vector lines)]
            (write-line content-stream 12 line-text 72 (- page-height 100 (* index 24)))))
        (.save document file))
      (.getAbsolutePath file))))

(defn create-two-column-pdf [file-path]
  (let [file (File. file-path)
        left-lines ["Colonne gauche premiere ligne."
                    "Colonne gauche deuxieme ligne."]
        right-lines ["Colonne droite premiere ligne."
                     "Colonne droite deuxieme ligne."]]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)
            page-width (.getWidth PDRectangle/A4)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (doseq [[index line-text] (map-indexed vector left-lines)]
            (write-line content-stream 12 line-text 72 (- page-height 100 (* index 24))))
          (doseq [[index line-text] (map-indexed vector right-lines)]
            (write-line content-stream 12 line-text (+ (/ page-width 2) 36)
                        (- page-height 100 (* index 24)))))
        (.save document file))
      (.getAbsolutePath file))))

(defn- centered-line-x [page-width font-size text]
  (let [font (PDType1Font. Standard14Fonts$FontName/HELVETICA)
        text-width (* font-size (count text) 0.5)]
    (max 36.0 (- (/ page-width 2.0) (/ text-width 2.0)))))

(defn create-centered-title-two-column-pdf [file-path]
  (let [file (File. file-path)
        title "TITRE CENTRE"
        subtitle "Sous-titre centre"
        left-lines ["Colonne gauche premiere ligne."
                    "Colonne gauche deuxieme ligne."]
        right-lines ["Colonne droite premiere ligne."
                     "Colonne droite deuxieme ligne."]]
    (with-open [document (PDDocument.)]
      (let [page (PDPage. PDRectangle/A4)
            page-height (.getHeight PDRectangle/A4)
            page-width (.getWidth PDRectangle/A4)]
        (.addPage document page)
        (with-open [content-stream (PDPageContentStream. document page)]
          (write-line content-stream 18 title
                      (centered-line-x page-width 18 title)
                      (- page-height 80))
          (write-line content-stream 12 subtitle
                      (centered-line-x page-width 12 subtitle)
                      (- page-height 110))
          (doseq [[index line-text] (map-indexed vector left-lines)]
            (write-line content-stream 12 line-text 72 (- page-height 180 (* index 24))))
          (doseq [[index line-text] (map-indexed vector right-lines)]
            (write-line content-stream 12 line-text (+ (/ page-width 2) 36)
                        (- page-height 180 (* index 24)))))
        (.save document file))
      (.getAbsolutePath file))))
