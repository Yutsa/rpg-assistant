(ns rpg-assistant-web.routes)

(defn parse-path [pathname]
  (let [parts (remove empty? (.split pathname "/"))]
    (case (first parts)
      "campaigns" (if-let [campaign-id (second parts)]
                    {:page :campaign-documents :campaign-id campaign-id}
                    {:page :campaigns})
      "documents" (cond
                    (and (= (nth parts 2 nil) "stat-blocks")
                         (nth parts 3 nil))
                    {:page :stat-block-detail
                     :document-id (second parts)
                     :stat-block-name (js/decodeURIComponent (nth parts 3))}

                    (= (nth parts 2 nil) "stat-blocks")
                    {:page :stat-blocks :document-id (second parts)}

                    (and (= (nth parts 2 nil) "chunks")
                         (nth parts 3 nil))
                    {:page :document-explorer
                     :document-id (second parts)
                     :chunk-id (nth parts 3)}

                    (second parts)
                    {:page :document-explorer :document-id (second parts)}

                    :else {:page :not-found})
      nil {:page :campaigns}
      {:page :not-found})))

(defn path-for [route]
  (case (:page route)
    :campaigns "/"
    :campaign-documents (str "/campaigns/" (:campaign-id route))
    :document-explorer (str "/documents/" (:document-id route))
    :stat-blocks (str "/documents/" (:document-id route) "/stat-blocks")
    :stat-block-detail (str "/documents/" (:document-id route)
                            "/stat-blocks/"
                            (js/encodeURIComponent (:stat-block-name route)))
  "/"))

(defn breadcrumbs [route]
  (let [base [{:label "Campagnes" :path "/"}]]
    (case (:page route)
      :campaigns base
      :campaign-documents (conj base {:label (:campaign-id route)
                                      :path (path-for route)})
      (:document-explorer :stat-blocks :stat-block-detail)
      (let [doc-id (:document-id route)]
        (cond-> (conj base {:label doc-id :path (str "/documents/" doc-id)})
          (= (:page route) :stat-blocks)
          (conj {:label "Fiches stats"
                 :path (str "/documents/" doc-id "/stat-blocks")})

          (= (:page route) :stat-block-detail)
          (conj {:label "Fiches stats"
                 :path (str "/documents/" doc-id "/stat-blocks")}
                {:label (:stat-block-name route)})))
      (conj base {:label "Page introuvable"}))))
