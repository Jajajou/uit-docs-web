# Slide 1. Bài toán thực tế tại UIT

- Tài liệu học vụ, học phí, học bổng, lịch đăng ký môn học và các quy định nội bộ đang phân tán ở nhiều nguồn khác nhau như website, PDF, thông báo, biểu mẫu và tài liệu nội bộ.
- Người dùng thường hỏi bằng ngôn ngữ tự nhiên, nhưng câu trả lời đúng lại phải tổng hợp từ nhiều văn bản khác nhau, không nằm nguyên vẹn trong một tài liệu duy nhất.
- Khó khăn lớn nhất không chỉ là tìm tài liệu liên quan, mà là xác định văn bản nào còn hiệu lực, áp dụng cho khóa nào, năm học nào và phạm vi nào.
- Nếu dùng tìm kiếm từ khóa hoặc RAG thông thường, hệ thống rất dễ lấy nhầm văn bản cũ nhưng có nội dung giống về mặt ngữ nghĩa.
- Vì vậy, hệ thống cần trả lời đúng nội dung, đúng văn bản hiện hành, đúng đối tượng áp dụng và có nguồn để đối chiếu.

# Slide 2. Mục tiêu của hệ thống

- Xây dựng một trợ lý AI có thể trả lời câu hỏi về tài liệu UIT theo cách có dẫn nguồn, có kiểm soát và có khả năng giải thích.
- Rút ngắn thời gian tra cứu của sinh viên, giảng viên và quản trị viên khi cần xác minh thông tin học vụ hoặc vận hành.
- Giảm rủi ro trả lời sai do dùng nhầm văn bản hết hiệu lực hoặc không đúng phạm vi áp dụng.
- Tạo một lớp sản phẩm web để quản lý vòng đời tài liệu, theo dõi ingestion, kiểm soát truy cập và khai thác tri thức đã index.
- Chuyển dữ liệu rời rạc thành một hệ thống hỏi đáp có cấu trúc, có khả năng mở rộng cho các nhóm tài liệu khác nhau.

# Slide 3. Kiến trúc tổng thể

- Hệ thống được tổ chức thành 4 lớp chính: thu thập dữ liệu, xử lý và indexing, kho tri thức và truy vấn, lớp web vận hành.
- Lớp thu thập dữ liệu tiếp nhận tài liệu từ website, URL, văn bản thô và thao tác tải lên thủ công.
- Lớp xử lý chịu trách nhiệm đọc nội dung, OCR nếu là PDF scan, trích xuất metadata và chuẩn hóa tài liệu trước khi đưa vào kho tri thức.
- Lớp truy vấn sử dụng pipeline LangGraph để hiểu câu hỏi, truy xuất dữ liệu, làm giàu metadata thời gian, rerank và sinh câu trả lời cuối cùng.
- Lớp web đóng vai trò BFF và giao diện thao tác, giúp người dùng chat, xem nguồn tài liệu, theo dõi lịch sử và quản trị tài liệu.
- Đây không phải một chatbot đơn khối, mà là một kiến trúc nhiều lớp để đảm bảo tính đúng đắn, khả năng kiểm soát và khả năng mở rộng.

# Slide 4. Nguồn dữ liệu và lớp ingestion

- Hệ thống có thể ingest từ nhiều dạng đầu vào như website UIT, URL cụ thể, file PDF, văn bản text và tài liệu nội bộ.
- Firecrawl đóng vai trò quan trọng trong việc thu thập nội dung web, chuyển web page thành dữ liệu sạch để downstream có thể xử lý.
- Với PDF hoặc tài liệu scan, hệ thống có thêm bước OCR để không bỏ sót nội dung nằm trong ảnh hoặc bản scan chất lượng thấp.
- Sau khi đọc được nội dung, hệ thống chuẩn hóa metadata gốc như tiêu đề, loại tài liệu, thời gian tạo, nguồn xuất phát và thông tin nhận diện.
- Mục tiêu của ingestion không chỉ là tải tài liệu về, mà là chuẩn bị tài liệu ở trạng thái đủ sạch để bước indexing có thể hiểu đúng ngữ cảnh.

# Slide 5. Pipeline indexing tài liệu

- Khi tài liệu đi vào hệ thống, pipeline indexing sẽ xác định loại tài liệu, đọc nội dung, OCR nếu cần và chia tài liệu thành các đơn vị có thể truy vấn.
- Hệ thống trích xuất các trường quan trọng như số hiệu văn bản, năm học, ngày bắt đầu hiệu lực, ngày hết hiệu lực, cohort áp dụng và quan hệ sửa đổi hoặc thay thế.
- Nội dung tài liệu sau đó được đưa vào lớp tri thức để phục vụ truy vấn ngữ nghĩa và truy vấn theo quan hệ.
- Metadata thời gian và metadata nghiệp vụ được lưu riêng để pipeline truy vấn có thể sử dụng trong giai đoạn rerank và grounding.
- Điểm mạnh của indexing là không coi tài liệu như text thuần, mà biến tài liệu thành tri thức có cấu trúc để dùng về sau.
- Đây là bước quyết định chất lượng toàn hệ thống, vì nếu metadata sai hoặc thiếu thì truy vấn sau này rất khó trả lời đúng.

# Slide 6. Metadata RAG Subgraph: điểm khác biệt kỹ thuật lớn nhất

- Phần nổi bật nhất của hệ thống là Metadata RAG Subgraph, chuyên dùng để trích metadata quan trọng từ tài liệu thay vì chỉ dựa vào regex cứng.
- Cách làm là chia tài liệu thành các đoạn, index tạm, rồi truy vấn ngược lại chính tài liệu đó để tìm các trường metadata có ý nghĩa vận hành.
- Nhờ đó, hệ thống có thể phát hiện ngữ cảnh như văn bản nào sửa đổi văn bản nào, hiệu lực bắt đầu khi nào, áp dụng cho khóa nào và thuộc năm học nào.
- Cách tiếp cận này mạnh hơn trích xuất theo pattern vì nó tận dụng ngữ cảnh ngôn ngữ, phù hợp với tài liệu hành chính thường có cấu trúc không đồng đều.
- Metadata RAG Subgraph là cầu nối giữa văn bản thô và tri thức có cấu trúc, từ đó tạo nền tảng cho temporal reranking và grounded answer.
- Đây là lý do hệ thống không chỉ “tìm đoạn văn giống câu hỏi”, mà còn có thể “đánh giá đoạn nào đúng trong bối cảnh thời gian hiện tại”.

# Slide 7. Kho tri thức và lớp lưu trữ

- Hệ thống kết hợp nhiều lớp lưu trữ để phục vụ các nhu cầu khác nhau trong pipeline.
- LightRAG được dùng như lớp truy xuất tri thức chính, hỗ trợ lấy chunk, quan hệ và ngữ cảnh phục vụ tổng hợp câu trả lời.
- Qdrant đảm nhiệm vai trò vector database cho truy vấn ngữ nghĩa, giúp tìm các đoạn tài liệu có nội dung gần với câu hỏi.
- PostgreSQL dùng để lưu metadata có cấu trúc, trạng thái tài liệu, lifecycle và các thông tin phục vụ quản trị, truy vết và kiểm soát.
- Việc tách lớp lưu trữ giúp hệ thống cân bằng giữa tốc độ truy xuất, khả năng biểu diễn quan hệ và khả năng kiểm soát nghiệp vụ.
- Đây là nền tảng để hệ thống vừa có thể tìm nhanh, vừa có thể kiểm tra được văn bản nào đang thực sự còn hiệu lực.

# Slide 8. Pipeline truy vấn hiện tại

- Luồng truy vấn hiện tại đi theo hướng LangGraph first, đặc biệt với admin và nội bộ, để tận dụng đầy đủ pipeline hiểu câu hỏi và rerank theo thời gian.
- Pipeline chuẩn gồm các bước chính: chuẩn hóa đầu vào, Agent 1 hiểu ý định câu hỏi, retrieve dữ liệu, enrich temporal metadata, rerank dữ liệu, Agent 3 sinh câu trả lời và định dạng output.
- Đây là kiến trúc 2 agent, 7 node, đơn giản hơn trước nhưng ổn định hơn và dễ kiểm soát hơn trong vận hành.
- Trong truy vấn, hệ thống không dừng ở việc lấy top chunk gần nhất, mà tiếp tục so sánh và ưu tiên những nguồn phù hợp nhất với bối cảnh năm học, hiệu lực và phạm vi áp dụng.
- Với public, hệ thống có lớp an toàn để tránh rò rỉ dữ liệu nội bộ, và chỉ dùng full LangGraph khi có cấu hình assistant public tương ứng.
- Ý nghĩa của pipeline này là biến truy vấn từ “semantic search + answer” thành “reasoned retrieval + grounded answer”.

# Slide 9. Temporal reranking và grounding

- Temporal reranking là cơ chế xếp hạng lại nguồn dựa trên yếu tố thời gian và hiệu lực, không chỉ dựa trên độ giống ngữ nghĩa.
- Nếu có nhiều văn bản cùng nói về một chủ đề, hệ thống sẽ ưu tiên văn bản còn hiệu lực, đúng năm học và đúng cohort hơn là văn bản cũ nhưng giống từ khóa.
- Grounding score được dùng để đo mức độ khớp thực sự giữa câu hỏi và nguồn trả về, dựa trên title, tags, excerpt, loại tài liệu và metadata thời gian.
- Với các câu hỏi kiểu “còn hiệu lực không”, “đang áp dụng không”, “có thay đổi không”, hệ thống sẽ không được kết luận mạnh nếu grounding chưa đủ chắc.
- Cách làm này giảm hiện tượng hallucination và giảm rủi ro suy luận quá mức từ các nguồn chỉ liên quan gián tiếp.
- Đây là lớp kỹ thuật rất quan trọng vì nó quyết định hệ thống có dám kết luận hay phải trả về trạng thái chưa đủ căn cứ.

# Slide 10. Lớp web và trải nghiệm người dùng

- Phần web không chỉ là giao diện chat, mà là lớp sản phẩm hóa toàn bộ hệ thống để người dùng thực sự thao tác được với dữ liệu.
- Giao diện hiện có các chức năng chính như chat hỏi đáp, lịch sử hội thoại, panel nguồn tài liệu, upload tài liệu, quản trị và theo dõi trạng thái xử lý.
- Hệ thống đã được điều chỉnh theo hướng UX dễ dùng hơn: rail lịch sử và rail nguồn tài liệu cố định theo viewport, có thể thu gọn hoặc mở rộng độc lập.
- Phần trả lời của assistant đã được định dạng lại để người dùng đọc nhanh hơn, nhấn mạnh “kết luận nhanh”, phần giải thích và phần nguồn đối chiếu.
- UI cũng đang được tinh chỉnh theo hướng giảm nhiễu thị giác và tăng khả năng kiểm tra nguồn, vì sản phẩm này phục vụ tác vụ tra cứu chính xác chứ không chỉ trò chuyện.
- Vai trò của lớp web là biến một pipeline AI phức tạp thành trải nghiệm đủ rõ ràng để sinh viên, giảng viên và quản trị viên đều có thể sử dụng.

# Slide 11. Điểm mạnh cốt lõi của hệ thống

- Điểm mạnh thứ nhất là kết hợp retrieval ngữ nghĩa với metadata thời gian, giúp hệ thống vượt lên trên RAG thông thường.
- Điểm mạnh thứ hai là có lớp quản trị tài liệu và vòng đời dữ liệu, nên hệ thống không chỉ trả lời mà còn hỗ trợ vận hành.
- Điểm mạnh thứ ba là có thể giải thích câu trả lời bằng nguồn đối chiếu, giúp tăng mức độ tin cậy và khả năng kiểm chứng.
- Điểm mạnh thứ tư là kiến trúc đủ mô-đun để thay đổi hoặc mở rộng từng lớp riêng như ingestion, indexing, retrieval hay UI mà không phải viết lại toàn bộ.
- Điểm mạnh thứ năm là phù hợp với bối cảnh đại học, nơi tài liệu thay đổi theo năm học, khóa học và phạm vi áp dụng rất rõ rệt.
- Nói ngắn gọn, giá trị lớn nhất của hệ thống là trả lời có căn cứ, có bối cảnh thời gian và có khả năng kiểm soát.

# Slide 12. Hạn chế hiện tại và bài học rút ra

- Chất lượng câu trả lời vẫn phụ thuộc mạnh vào chất lượng metadata và chất lượng grounding của từng nguồn được retrieve.
- Một số luồng public vẫn cần cấu hình đầy đủ assistant public để có thể dùng full LangGraph mà vẫn bảo đảm tách biệt dữ liệu nội bộ.
- UI đã cải thiện nhưng vẫn cần tiếp tục tối ưu về độ mượt, khả năng đọc nhanh và giảm các thành phần thị giác chưa thật sự cần thiết.
- Một số môi trường local hoặc test chưa thật sự “green” hoàn toàn, cho thấy bài toán vận hành và đồng bộ môi trường vẫn là điểm cần đầu tư.
- Bài học quan trọng là với tài liệu hành chính, tối ưu model thôi là không đủ; phải tối ưu orchestration, retrieval, grounding và lifecycle dữ liệu.
- Hệ thống càng gần sản phẩm thật thì càng cần kết hợp cả kỹ thuật AI lẫn tư duy sản phẩm và tư duy vận hành.

# Slide 13. Kết luận và hướng phát triển

- Hệ thống UIT_DOCS_AGENT là một nền tảng hỏi đáp tài liệu có định hướng rõ ràng: đúng nguồn, đúng hiệu lực, đúng đối tượng và có thể kiểm chứng.
- Giá trị cốt lõi của hệ thống không nằm ở việc “trả lời hay như chatbot”, mà nằm ở việc “trả lời đúng và có căn cứ trong bối cảnh UIT”.
- Về mặt kỹ thuật, điểm đáng trình bày nhất là Metadata RAG Subgraph, temporal reranking và truy vấn LangGraph theo hướng grounded answer.
- Về mặt sản phẩm, điểm đáng trình bày nhất là lớp web quản trị và trải nghiệm đối chiếu nguồn giúp người dùng hiểu và tin vào câu trả lời.
- Hướng phát triển tiếp theo là hoàn thiện public LangGraph assistant, tăng chất lượng evaluation, bổ sung telemetry cho từng truy vấn và tiếp tục tối ưu UX.
- Nếu phát triển tiếp đúng hướng, hệ thống có thể trở thành nền tảng tra cứu tri thức học vụ và vận hành có độ tin cậy cao cho toàn bộ UIT.
