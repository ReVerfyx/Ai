package studio.reverfyx.ai;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.view.View;

public class LineIconView extends View {
    public static final int MENU=1, SEARCH=2, EDIT=3, MORE=4, IMAGE=5, LIBRARY=6,
            FOLDER=7, CODE=8, CLOCK=9, PLUGIN=10, CHAT=11, PLUS=12, MIC=13,
            EFFORT=14, FILE=15, CAMERA=16, PHOTO=17, SHARE=18, PIN=19,
            ARCHIVE=20, TRASH=21, HOME=22, CHECK=23, SEND=24;

    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private int kind;
    private int color = 0xff111111;

    public LineIconView(Context c, int kind) {
        super(c);
        this.kind = kind;
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeCap(Paint.Cap.ROUND);
        p.setStrokeJoin(Paint.Join.ROUND);
        p.setStrokeWidth(dp(2.2f));
    }

    public void setIconColor(int c) { color = c; invalidate(); }
    public void setKind(int k) { kind = k; invalidate(); }
    private float dp(float v){ return v * getResources().getDisplayMetrics().density; }

    @Override protected void onDraw(Canvas c) {
        super.onDraw(c);
        p.setColor(color);
        float w=getWidth(), h=getHeight(), cx=w/2f, cy=h/2f, s=Math.min(w,h);
        float l=cx-s*.28f, r=cx+s*.28f, t=cy-s*.28f, b=cy+s*.28f;
        Path q=new Path();
        switch(kind){
            case MENU:
                c.drawLine(l,cy-s*.12f,r,cy-s*.12f,p);
                c.drawLine(l,cy+s*.12f,cx+s*.08f,cy+s*.12f,p); break;
            case SEARCH:
                c.drawCircle(cx-s*.05f,cy-s*.05f,s*.18f,p);
                c.drawLine(cx+s*.08f,cy+s*.08f,r,b,p); break;
            case EDIT:
                c.drawRect(l,cy-s*.18f,cx+s*.12f,b,p);
                c.drawLine(cx-s*.02f,cy+s*.08f,r,t,p);
                c.drawLine(r,t,r-s*.08f,t-s*.08f,p); break;
            case MORE:
                p.setStyle(Paint.Style.FILL);
                c.drawCircle(cx,cy-s*.16f,dp(2.1f),p); c.drawCircle(cx,cy,dp(2.1f),p); c.drawCircle(cx,cy+s*.16f,dp(2.1f),p);
                p.setStyle(Paint.Style.STROKE); break;
            case IMAGE:
                c.drawRoundRect(l,t,r,b,dp(3),dp(3),p);
                c.drawCircle(cx-s*.12f,cy-s*.10f,s*.045f,p);
                q.moveTo(l+s*.05f,b-s*.07f); q.lineTo(cx-s*.06f,cy+s*.02f); q.lineTo(cx+s*.04f,cy+s*.12f); q.lineTo(r-s*.05f,cy-s*.01f); c.drawPath(q,p);
                break;
            case LIBRARY:
                c.drawRoundRect(l,t,l+s*.13f,b,dp(2),dp(2),p);
                c.drawRoundRect(cx-s*.06f,t,cx+s*.06f,b,dp(2),dp(2),p);
                c.drawRoundRect(r-s*.13f,t,r,b,dp(2),dp(2),p); break;
            case FOLDER:
                q.moveTo(l,t+s*.08f); q.lineTo(cx-s*.08f,t+s*.08f); q.lineTo(cx, t+s*.16f); q.lineTo(r,t+s*.16f); q.lineTo(r,b); q.lineTo(l,b); q.close(); c.drawPath(q,p); break;
            case CODE:
                q.moveTo(cx-s*.10f,cy-s*.15f); q.lineTo(l,cy); q.lineTo(cx-s*.10f,cy+s*.15f);
                q.moveTo(cx+s*.10f,cy-s*.15f); q.lineTo(r,cy); q.lineTo(cx+s*.10f,cy+s*.15f);
                c.drawPath(q,p); break;
            case CLOCK:
                c.drawCircle(cx,cy,s*.25f,p); c.drawLine(cx,cy,cx,cy-s*.13f,p); c.drawLine(cx,cy,cx-s*.10f,cy+s*.07f,p); break;
            case PLUGIN:
                c.drawCircle(cx,cy,s*.23f,p); c.drawCircle(cx,cy,s*.10f,p); c.drawLine(cx-s*.28f,cy,cx-s*.12f,cy,p); c.drawLine(cx+s*.12f,cy,cx+s*.28f,cy,p); break;
            case CHAT:
                c.drawRoundRect(l,t,r,b-s*.08f,dp(8),dp(8),p); q.moveTo(cx-s*.09f,b-s*.08f); q.lineTo(cx-s*.15f,b+s*.02f); q.lineTo(cx+s*.01f,b-s*.08f); c.drawPath(q,p); break;
            case PLUS:
                c.drawLine(cx,t,cx,b,p); c.drawLine(l,cy,r,cy,p); break;
            case MIC:
                c.drawRoundRect(cx-s*.09f,t,cx+s*.09f,cy+s*.05f,dp(8),dp(8),p);
                q.moveTo(l+s*.05f,cy); q.quadTo(cx, b-s*.05f,r-s*.05f,cy); c.drawPath(q,p);
                c.drawLine(cx,cy+s*.19f,cx,b,p); c.drawLine(cx-s*.10f,b,cx+s*.10f,b,p); break;
            case EFFORT:
                c.drawCircle(cx,cy,s*.22f,p); c.drawArc(cx-s*.13f,cy-s*.13f,cx+s*.13f,cy+s*.13f,205,220,false,p); c.drawLine(cx,cy,cx+s*.14f,cy-s*.08f,p); break;
            case FILE:
                q.moveTo(l,t); q.lineTo(cx+s*.07f,t); q.lineTo(r,cy-s*.08f); q.lineTo(r,b); q.lineTo(l,b); q.close(); c.drawPath(q,p); c.drawLine(cx+s*.07f,t,cx+s*.07f,cy-s*.08f,p); c.drawLine(cx+s*.07f,cy-s*.08f,r,cy-s*.08f,p); break;
            case CAMERA:
                c.drawRoundRect(l,cy-s*.14f,r,b,dp(5),dp(5),p); c.drawCircle(cx,cy+s*.05f,s*.12f,p); c.drawLine(cx-s*.11f,cy-s*.14f,cx-s*.05f,t,p); c.drawLine(cx-s*.05f,t,cx+s*.08f,t,p); c.drawLine(cx+s*.08f,t,cx+s*.13f,cy-s*.14f,p); break;
            case PHOTO:
                c.drawRoundRect(l,t,r,b,dp(4),dp(4),p); c.drawCircle(cx-s*.12f,cy-s*.11f,s*.04f,p); q.moveTo(l+s*.04f,b-s*.05f); q.lineTo(cx-s*.07f,cy+s*.02f); q.lineTo(cx+s*.02f,cy+s*.11f); q.lineTo(r-s*.04f,cy-s*.02f); c.drawPath(q,p); break;
            case SHARE:
                c.drawCircle(l+s*.08f,cy,s*.045f,p); c.drawCircle(r-s*.08f,t+s*.08f,s*.045f,p); c.drawCircle(r-s*.08f,b-s*.08f,s*.045f,p); c.drawLine(l+s*.12f,cy,r-s*.13f,t+s*.11f,p); c.drawLine(l+s*.12f,cy,r-s*.13f,b-s*.11f,p); break;
            case PIN:
                q.moveTo(cx-s*.08f,t); q.lineTo(cx+s*.11f,cy-s*.02f); q.lineTo(cx+s*.04f,cy+s*.05f); q.lineTo(cx+s*.11f,cy+s*.12f); q.lineTo(cx-s*.02f,cy+s*.17f); q.lineTo(l,cy+s*.08f); q.close(); c.drawPath(q,p); c.drawLine(cx-s*.05f,cy+s*.13f,cx-s*.18f,b,p); break;
            case ARCHIVE:
                c.drawRoundRect(l,cy-s*.12f,r,b,dp(3),dp(3),p); c.drawRect(l-s*.02f,t,r+s*.02f,cy-s*.10f,p); c.drawLine(cx-s*.07f,cy+s*.04f,cx+s*.07f,cy+s*.04f,p); break;
            case TRASH:
                c.drawRoundRect(cx-s*.15f,cy-s*.12f,cx+s*.15f,b,dp(2),dp(2),p); c.drawLine(cx-s*.20f,cy-s*.17f,cx+s*.20f,cy-s*.17f,p); c.drawLine(cx-s*.07f,t,cx+s*.07f,t,p); c.drawLine(cx-s*.07f,t,cx-s*.10f,cy-s*.17f,p); c.drawLine(cx+s*.07f,t,cx+s*.10f,cy-s*.17f,p); break;
            case HOME:
                q.moveTo(l,cy); q.lineTo(cx,t); q.lineTo(r,cy); q.lineTo(r,b); q.lineTo(cx+s*.08f,b); q.lineTo(cx+s*.08f,cy+s*.09f); q.lineTo(cx-s*.08f,cy+s*.09f); q.lineTo(cx-s*.08f,b); q.lineTo(l,b); q.close(); c.drawPath(q,p); break;
            case CHECK:
                q.moveTo(l,cy); q.lineTo(cx-s*.03f,b-s*.05f); q.lineTo(r,t+s*.05f); c.drawPath(q,p); break;
            case SEND:
                c.drawLine(cx,b,cx,t+s*.04f,p);
                c.drawLine(cx,t+s*.04f,cx-s*.14f,cy-s*.02f,p);
                c.drawLine(cx,t+s*.04f,cx+s*.14f,cy-s*.02f,p); break;
        }
    }
}
