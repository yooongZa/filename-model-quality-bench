# 다이어그램 수정

`flow.mmd`의 상자 문구와 화살표를 수정합니다. README는 GitHub의 동적 뷰어에 의존하지 않도록 렌더링한 SVG를 표시합니다. PNG는 발표 자료에도 사용할 수 있습니다.

저장소 루트에서 다음 명령으로 두 이미지를 갱신합니다. 최초 실행 시 npm이 렌더러를 설치할 수 있습니다.

```bash
npx --yes --package @mermaid-js/mermaid-cli@11.15.0 mmdc -i docs/diagrams/flow.mmd -o docs/diagrams/flow.svg -c docs/diagrams/mermaid.json -w 1200 -b white -s 2
npx --yes --package @mermaid-js/mermaid-cli@11.15.0 mmdc -i docs/diagrams/flow.mmd -o docs/diagrams/flow.png -c docs/diagrams/mermaid.json -w 1200 -b white -s 2
```

문구나 흐름을 바꾸면 SVG와 PNG를 함께 갱신하세요. [Mermaid CLI 공식 안내](https://github.com/mermaid-js/mermaid-cli)를 따릅니다. 다이어그램은 코드 구조 설명이며 실제 GPU 실행 결과를 의미하지 않습니다.
