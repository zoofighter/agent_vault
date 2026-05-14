옵시디언 볼트가 커지면 뉴스 검색하고 매칭하는데 시간이 많이 걸리지 않을까
클로드 md 작성 

https://finance.naver.com/research/company_list.naver
종목을 찾아서 한국 종목 research 폴더에 요약해서 저장 로컬 llm 이용 

https://finance.naver.com/research/company_list.naver   에서  research로 해당 기업이 내용을 요약하는 배치를 구현해줘 실행은 일자 및 기간으로 해줘

https://finance.naver.com/research/industry_list.naver
pdf를 빨리 검색하고 companies.csv 중 미국 기업들을 찾아 해당 기업의 research 폴더에 저장 로컬 llm 이용 요약 하는 배치를 구현 

폴더 구조를 변경 미국 기업들과 아시아 기업들로 분리  companies.csv 를 조사해서 미국기업 아시아 기업으로 분리  


llm을 사용하는 부분 


-- 위 소스들을 가지고 블로그나 유투브를 생성할 수 있을까.. 


추가적으로 나에게 지시를 내리는 agent를 여기에 추가 해줘 예를 들어 스케줄로 감시해서 중요 보고서를 찾아 보라고 할 수도 있고 중요 테마를 확인해 보라고 나에게 명령어를 내릴  있고 그래서 내가 심층적 분석할 수 있게 그리고 그것을 llm이 도와 주는 건데 이건 로컬 llm + 클라우드 llm을 사용해 됨 

--- 심층분석을 -->  분석 결과 + 커멘트 --> 투자로 이어지게  -- 리포트
--- 심층 분석 --->